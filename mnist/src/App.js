import './App.scss';

import React, { Component, useEffect, useState } from 'react';

const MODEL_NAME = 'mnist';
const API_BASE_URL = '/';


function Model(props) {
  let { model } = props;
  return (
    <p>
      <h2>Model</h2>
      <pre>Name: {model.name}</pre>
      <pre>Created at: {model.created_at}</pre>
      <pre>Updated at: {model.updated_at}</pre>
      <pre>ID: {model.id}</pre>
    </p>
  );
};

function Job(props) {
  let { job } = props;
  if (!job) {
    return null;
  }

  return (
    <p>
      <h2>Job</h2>
      <pre>ID: {job.id}</pre>
      <pre>Created at: {job.created_at}</pre>
      <pre>Updated at: {job.updated_at}</pre>
      <pre>Status: {job.status}</pre>
      <pre>Result path: {job.result_path}</pre>
    </p>
  );
};

function Result(props) {
  let { job } = props;

  const [result, setResult] = useState();

  useEffect(() => {
    if (!job || !job.result_path) {
      return;
    }

    fetch(`${API_BASE_URL}files/${job.result_path}`)
      .then(res => res.text())
      .then(text => {
        setResult(text);
      });
  })

  if (!job || !job.result_path) {
    return null;
  }

  return (
    <p>
      <h2>Result</h2>
      <pre>Path: {job.result_path}</pre>
      <pre>Result: {result}</pre>
    </p>
  );
}

class App extends Component {
  state = {
    model: null,
    argument_path: null,
    result_path: null,
    file: null,
    image: null,
    job: null,

    checker: null,
  }

  componentDidMount() {
    fetch(`${API_BASE_URL}models/`)
      .then(res => res.json())
      .then(data => {
        let model = data.find(model => model.name === MODEL_NAME);
        this.setState({ model: model });
      })
  }

  onChangeHandler(e) {
    let file = e.target.files[0];
    console.log(file);
    let reader = new FileReader();

    reader.readAsDataURL(file);
    reader.onload = (e) => {
      this.setState({
        file: file,
        image: e.target.result,
      });
    };
  }

  onUploadHandler(_e) {
    // Upload image
    let formData = new FormData();
    formData.append('file', this.state.file);
    fetch(`${API_BASE_URL}files/`, {
      method: 'POST',
      body: formData,
    })
      .then(res => res.json())
      .then(file => {
        this.setState({ argument_path: file.path });
      })
    ;
  }

  onSubmitHandler(_e) {
    let { model, argument_path } = this.state;
    if (!argument_path || !model) {
      return;
    }

    // Create job
    let data = {
      model_id: model.id,
      argument_path,
    };

    fetch(`${API_BASE_URL}jobs/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
      .then(res => res.json())
      .then((job) => {
        // Create cheker interval
        let checker = setInterval(this.refreshJob.bind(this), 1000);
        this.setState({
          checker: checker,
          job: job,
        });
      });
  }

  refreshJob() {
    let { job, checker } = this.state;
    if (!job || job.status === 'failed' || job.status === 'completed') {
      clearInterval(checker);
      this.setState({
        checker: null,
      });
      return;
    }

    fetch(`${API_BASE_URL}jobs/${job.id}`)
      .then(res => res.json())
      .then(data => {
        this.setState({
          job: data,
        });
      });
  }

  render() {
    let { model } = this.state;
    if (!model) {
      return <div>Loading...</div>
    }

    return (
      <>
        <Model model={model} />

        <div id="input">
          <h2>Input image</h2>
          <input type="file" onChange={this.onChangeHandler.bind(this)} />
          <img id="input_img" src={this.state.image} alt="Input"/>
          <button onClick={this.onUploadHandler.bind(this)}>Upload</button>
          {this.state.argument_path && <p>Path: {this.state.argument_path}</p>}
        </div>

        <p>
          <h2>Run</h2>
          <button onClick={this.onSubmitHandler.bind(this)}>Run</button>
        </p>

        <Job job={this.state.job} />

        <Result job={this.state.job} />
      </>
    );
  }
}


export default App;
