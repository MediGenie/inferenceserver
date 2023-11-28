import os
import shutil
import socket
import stat
import subprocess
import tempfile
import time
import venv

import appdirs
import numpy as np

from . import models, object_storage
from .worker_templates import common


class ModelWorker:

    def __init__(self, model: models.Model):
        self.model = model

        self.setup()

    def setup(self):
        self.install_model_files()
        self.start_model_worker()

    def install_model_files(self):
        if not os.path.exists(self.venv_dir):
            venv.create(self.venv_dir, with_pip=True)

        # Extract model files to venv/model
        # TODO: Copy from object storage
        res = object_storage.get_object(self.model.module_path)
        filename = os.path.basename(self.model.module_path)
        archive_path = os.path.join(self.venv_dir, filename)
        with open(archive_path, 'wb') as file:
            file.write(res.read())
        shutil.unpack_archive(archive_path, self.model_dir)

        setup_path = os.path.join(self.model_dir, 'setup')
        if os.path.exists(setup_path):
            # Ensure setup script is executable
            current_mode = stat.S_IMODE(os.lstat(setup_path).st_mode)
            os.chmod(setup_path, current_mode | stat.S_IXUSR)
            # Run setup script inside venv
            print('Running setup script!!!!')
            subprocess.run(
                ['bash', '-c', '. ../bin/activate && ./setup'],
                cwd=self.model_dir
            )
        else:
            # Install model dependencies from venv/model/requirements.txt
            subprocess.run(
                [
                    os.path.join(self.venv_dir, 'bin', 'pip'),
                    'install',
                    '-r',
                    os.path.join(self.model_dir, 'requirements.txt'),
                ],
                stdout=subprocess.DEVNULL,
            )

        # Ensure install numpy
        subprocess.run(
            [
                os.path.join(self.venv_dir, 'bin', 'pip'),
                'install',
                'numpy',
            ],
            stdout=subprocess.DEVNULL,
        )

        # Copy init.py to venv
        try:
            shutil.copytree(self.template_dir, self.venv_dir, dirs_exist_ok=True)
        except FileExistsError:
            pass

    def start_model_worker(self):

        self.process = subprocess.Popen(
            [
                os.path.join(self.venv_dir, 'bin', 'python'),
                os.path.join(self.venv_dir, "init.py")
            ],
            cwd=self.venv_dir,
        )

    def preprocess(self, argument_path: str) -> bytes:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        local_argument_path = tempfile.mktemp(prefix='ais_')
        object_storage.fget_object(argument_path, local_argument_path)

        for i in range(3):
            try:
                sock.connect(self.socket_path)
            except (ConnectionRefusedError, FileNotFoundError):
                delay = 2 ** i
                print(f'Connection refused, retrying in {delay}')
                time.sleep(delay)
            else:
                break

        msg = common.CMD_PREPROCESS + common.SEPARATOR + local_argument_path.encode()

        # TODO: Handle large files
        try:
            sock.sendall(msg)
            resp, arg = sock.recv(1000000).split(common.SEPARATOR, 1)
        except Exception as e:
            error_path = os.path.join(self.venv_dir, 'error.txt')
            if os.path.exists(error_path):
                # Check error.txt
                with open(os.path.join(self.venv_dir, 'error.txt'), 'r') as f:
                    error = f.read()
                raise RuntimeError(error)
            else:
                raise e

        os.unlink(local_argument_path)

        if resp == common.RESP_ERR:
            raise RuntimeError(arg.decode())

        return arg

    def inference(self, encoded_inputs: bytes) -> bytes:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        for i in range(3):
            try:
                sock.connect(self.socket_path)
            except ConnectionRefusedError:
                delay = 2 ** i
                print(f'Connection refused, retrying in {delay}')
                time.sleep(delay)
            else:
                break

        msg = common.CMD_INFERENCE + common.SEPARATOR + encoded_inputs

        sock.sendall(msg)

        resp, arg = sock.recv(10000).split(common.SEPARATOR, 1)
        if resp == common.RESP_ERR:
            raise RuntimeError(arg.decode())

        return arg

    def postprocess(self, job: models.Job, encoded_outputs: bytes) -> str:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        for i in range(3):
            try:
                sock.connect(self.socket_path)
            except ConnectionRefusedError:
                delay = 2 ** i
                print(f'Connection refused, retrying in {delay}')
                time.sleep(delay)
            else:
                break

        msg = common.CMD_POSTPROCESS + common.SEPARATOR + encoded_outputs

        sock.sendall(msg)

        resp, arg = sock.recv(10000).split(common.SEPARATOR, 1)
        if resp == common.RESP_ERR:
            raise RuntimeError(arg.decode())

        result_local_path = arg.decode()
        result_object_path = f'results/{job.id}'
        object_storage.fput_object(result_object_path, result_local_path)
        os.unlink(result_local_path)

        return result_object_path

    # TODO: Remove this
    def run_job(self, argument_path):
        output_path = tempfile.mkdtemp(prefix='ais_')

        with open(self.input_fifo, 'w') as f:
            f.write(f'{argument_path}|{output_path}')

        # Wait for the worker to finish
        with open(self.output_fifo, 'r') as f:
            f.readline()

        # Check error
        if os.path.isfile(self.error_file):
            print('Got error')
            with open(self.error_file, 'r') as f:
                raise RuntimeError(f.read())

        return output_path

    def stop(self):
        print(f'Killing model {self.model.id}')
        self.process.kill()
        self.process.terminate()

    @property
    def venv_dir(self):
        return os.path.join(
            appdirs.user_cache_dir('ais_'),
            'venvs',
            f'model_{self.model.id}',
        )

    @property
    def model_dir(self):
        return os.path.join(
            self.venv_dir,
            'model',
        )

    @property
    def socket_path(self):
        return os.path.join(
            self.venv_dir,
            common.SOCK_NAME,
        )

    @property
    def template_dir(self):
        return os.path.join(
            os.path.dirname(__file__),
            'worker_templates',
        )
