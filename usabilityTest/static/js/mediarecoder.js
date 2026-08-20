'use strict';
jQuery.noConflict();
$ = jQuery;

$(document).ready(function () {
  console.log("Task initiated!");

  // Declare variabes here
  let mediaRecorder;
  let recordedBlobs;
  let camStream;

  const audioConstraints = {
    audio: {
      echoCancellation: { exact: true }
    },
    video: false,
  };

  const videoConstraints = {
    video: true,
    audio: false,
  };

  const startTaskRec = document.querySelector('span#startrec');
  const endTaskRec = document.querySelector('button#finishTask');
  const recordedVideo = document.querySelector('video#recorded');
  const retakeButton = document.querySelector('button#redoTask');
  const camVideo = document.querySelector('video#cam');
  const camOnOff = document.querySelector('button#cam-status');
  const taskDone = document.querySelector('span#TaskDone');




  // Functions


  function QuestionHandler() {
    $(".curr-task .step:nth-child(2)").removeClass('step-active');
    $(".curr-task .step:nth-child(2)").addClass('step-done');
    $(".curr-task .step:nth-child(2) i").removeAttr("style");
    $(".curr-task .step:nth-child(3)").addClass('step-active');
    $(".taskInfo").collapse("hide");
    $(".TaskDone").css("display", "none");
  }


  async function StartCamera() {
    try {
      await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      }).then(screenStream => {
        camVideo.srcObject = screenStream;
        camStream = screenStream;
        $(".cam-stream").removeAttr("style");
      });
      $(".cam-stream video").show();
      $("#cam-status").css("color", "#0072ff");
      $("#cam-status").val("on");
      $("#cam-status span").text("Turn off ");
    } catch (err) {
      console.log(err); /* handle the error */
    if (err.name == "NotFoundError" || err.name == "DevicesNotFoundError") {
        alert("Webcam not found");
    } else if (err.name == "NotReadableError" || err.name == "TrackStartError") {
        alert("Media already in use, make sure you closed other applicaions using webcam"); 
    } else if (err.name == "OverconstrainedError" || err.name == "ConstraintNotSatisfiedError") {
        alert("Video resolution not sufficient"); 
    } else if (err.name == "NotAllowedError" || err.name == "PermissionDeniedError") {
      alert("Provide permissions to Webcam to start test");  
    } else if (err.name == "TypeError" || err.name == "TypeError") {
        alert("No data available from media"); 
    } else {
        alert("something went wrong, please try again"); 
    }
      location.reload();
    }
  }

  function StopCamera() {
    camVideo.srcObject = null;
    $(".cam-stream video").hide();
    $("#cam-status").css("color", "black");
    $("#cam-status").val("off");
    $("#cam-status span").text("Turn on ");
    if (camStream) {
      camStream.getTracks().forEach(function (track) {
        if (track.readyState == 'live' && track.kind === 'video') {
          track.stop();
        }
      });

    }

  }


  function CameraHandler() {
    if ($(this).val() === "off") {
      setTimeout(StartCamera, 100);

    }
    else if ($(this).val() === "on") {
      setTimeout(StopCamera, 100);
    }
  }

  function GetCookie(name) {
    if (!document.cookie) {
      return null;
    }

    const xsrfCookies = document.cookie.split(';')
      .map(c => c.trim())
      .filter(c => c.startsWith(name + '='));

    if (xsrfCookies.length === 0) {
      return null;
    }
    return decodeURIComponent(xsrfCookies[0].split('=')[1]);
  }

  function UploadRecordingToServer() {

    const blob = new Blob(recordedBlobs, { type: 'video/webm' });
    var cookie = GetCookie('csrftoken');
    var currntTask = $("#taskid").val();
    var fd = new FormData();
    fd.append('file', blob);
    fd.append('taskid', currntTask);
    $('#load').removeAttr('style');
    $.ajax({
      type: 'POST',
      url: '/upload/',
      data: fd,
      processData: false,
      contentType: false,
      enctype: 'multipart/form-data',
      headers: { 'X-CSRFToken': cookie },
      success: function (data) {
        console.log("success");
        console.log(data);
        $("#TaskInfo").hide();
        $("#redoInfo").removeAttr('style');
        $('.toast').toast('dispose');
        $(".recorded-output").removeAttr("style");
        setTimeout(stepperHandler,100);
      },
      failure: function (data) {
        console.log("failure");
        console.log(data);
        $('.toast').toast('dispose');
      },

      complete: function () {
        $('#load').hide();
        $("#reviewInfo").show();
      }
    });
  }

  async function updateValidationAnswer() {
    var cookie = GetCookie('csrftoken');
    var answer = $("#taskq").val();
    var taskid = $("#taskid").val();
    var fd = new FormData();

    fd.append('taskq', answer);
    fd.append('taskid', taskid);
    $.ajax({
      type: 'POST',
      url: '/validate/',
      data: fd,
      processData: false,
      contentType: false,
      enctype: 'multipart/form-data',
      headers: { 'X-CSRFToken': cookie },
      success: function (data) {
        console.log("success");
        console.log(data);
      },
      failure: function (data) {
        console.log("failure");
        console.log(data);
      },
    });
  }

  async function ViewRecorded() {
    const superBuffer = new Blob(recordedBlobs, { type: 'video/webm' });
    recordedVideo.src = null;
    recordedVideo.srcObject = null;
    recordedVideo.src = window.URL.createObjectURL(superBuffer);
    recordedVideo.controls = true;
    recordedVideo.play();
  }

  function handleDataAvailable(event) {
    console.log('handleDataAvailable', event);
    if (event.data && event.data.size > 0) {
      recordedBlobs.push(event.data);
    }
  }


  async function handleVolume(audioContext) {
    const soundMeter = window.soundMeter = new SoundMeter(audioContext);
    soundMeter.connectToSource(window.stream);

  }

  async function stopRecording() {

    if (mediaRecorder.state == "recording") {
      await mediaRecorder.stop();
      await window.audioContext.close();
    }
    StopIdleTimeCheck();
  }

  async function startRecording() {
    recordedBlobs = [];
    let options = { mimeType: 'video/webm;codecs=vp9,opus' };
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
      console.error(`${options.mimeType} is not supported`);
      options = { mimeType: 'video/webm;codecs=vp8,opus' };
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        console.error(`${options.mimeType} is not supported`);
        options = { mimeType: 'video/webm' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          console.error(`${options.mimeType} is not supported`);
          options = { mimeType: '' };
        }
      }
    }

    try {
      mediaRecorder = new MediaRecorder(window.stream, options);
      window.audioContext = new AudioContext();
    } catch (e) {
      console.error('Exception while creating MediaRecorder:', e.name);
      return;
    }
    console.log('Created MediaRecorder', mediaRecorder, 'with options', options);
    mediaRecorder.onstop = (event) => {
      console.log('Recorder stopped: ', event);
      console.log('Recorded Blobs: ', recordedBlobs);
    };
    mediaRecorder.ondataavailable = handleDataAvailable;
    mediaRecorder.start();
    console.log('MediaRecorder started', mediaRecorder);
    handleVolume(window.audioContext);

    $("#ifr-dsp").removeAttr("style");
    $(".taskQ").removeAttr("style");
    startTaskRec.hidden = true;
    $(".TaskDone").removeAttr("style");

  }

  async function handleSuccess(stream) {
    try {
      console.log('getUserMedia() got stream:', stream);
      window.stream = stream;
      new Promise(startRecording).then(handleVolume);
    } catch (e) {
      console.log('Stream didnot received :', e)
      location.reload();
    }



  }


  async function Start_Screen_Share(audioSettingts, videoSettings) {
    if (navigator.mediaDevices === undefined) {
      alert("your browser doesnot support this test");
    }
    try {
      let screenStream = await navigator.mediaDevices.getDisplayMedia(videoSettings);
      let mic = await navigator.mediaDevices.getUserMedia(audioSettingts);
      screenStream.addTrack(mic.getTracks()[0]);
      handleSuccess(screenStream);
    } catch (err) {
      console.log(err); /* handle the error */
    if (err.name == "NotFoundError" || err.name == "DevicesNotFoundError") {
        alert("No Screen source or Mic not found");
    } else if (err.name == "NotReadableError" || err.name == "TrackStartError") {
        alert("Media already in use, make sure you closed other applications using screenshare, mic and webcam"); 
    } else if (err.name == "OverconstrainedError" || err.name == "ConstraintNotSatisfiedError") {
        alert("Audio / Video resolution not sufficient"); 
    } else if (err.name == "NotAllowedError" || err.name == "PermissionDeniedError") {
      alert("Provide permissions to Mic/Webcam/screenshare to start test");  
    } else if (err.name == "TypeError" || err.name == "TypeError") {
        alert("No data available from media"); 
    } else {
        alert("something went wrong, please try again"); 
    }
      location.reload();
    }

  }

  function stepperHandler() {

    $(".taskQ").hide();
    $(".cam-stream").hide();
    $(".curr-task .step:nth-child(n+2):nth-last-child(n+2)").removeClass('step-active');
    $(".curr-task .step:nth-child(n+2):nth-last-child(n+2)").addClass('step-done');
    $(".curr-task .step:nth-child(n+2):nth-last-child(n+2) i").removeAttr("style");
    $(".curr-task .step:nth-child(n+2):nth-last-child(n+2) .taskInfo").hide();
    $(".curr-task .step:nth-child(4)").addClass('step-active');
  }

  function EndTask(e) {
    e.preventDefault();
    if ($("#taskq").val()) {

      try {
        setTimeout(updateValidationAnswer, 100);
        new Promise(stopRecording);
        $("#ifr-rec iframe").css("display", "none");
        setTimeout(UploadRecordingToServer, 500);
      } catch (error) {
        console.log('error in ending task :', error)
      }


      if (stream) {
        stream.getVideoTracks()[0].stop();
        stream.getTracks().forEach(function (track) {
          if (track.readyState == 'live' && track.kind === 'audio') {
            track.stop();
          }
        });
      }
      if (camStream) {
        camStream.getTracks().forEach(function (track) {
          if (track.readyState == 'live' && track.kind === 'video') {
            track.stop();
          }
        });
      }
    } else {
      alert("Please enter the answer");
    }
  }

  async function BeginTask() {
    try {
      await Start_Screen_Share(audioConstraints, videoConstraints);
    } catch (e) {
      console.log("Error in ScreenShare :", e)
    }
    setTimeout(StartCamera, 300);
  };


  function ValidateSelect() {
    var radioValue = $("#taskq").val();
    if (radioValue) {
      $('#finishTask').removeAttr("disabled");
    }
  };

  function RepeatTask() {

    var currntTask = $("#taskid").val();
    window.location.href = "/test/" + currntTask;

  }

  $("input[type=radio]").on("click", ValidateSelect);
  startTaskRec.addEventListener('click', BeginTask)
  retakeButton.addEventListener('click', () => { setTimeout(location.reload(), 1000) });
  endTaskRec.addEventListener('click', EndTask);
  camOnOff.addEventListener('click', CameraHandler);
  taskDone.addEventListener('click', QuestionHandler);

  $('.video').parent().click(function () {
    $(this).children(".playpause").fadeOut();
    ViewRecorded();
  });
  $('#contactUs').tooltip();
  $(".footer").hide();
  $(".collapsetaskques").collapse("hide");
  $(".helpandinstructions").collapse("hide");
  $('.collapse').collapse();

});

