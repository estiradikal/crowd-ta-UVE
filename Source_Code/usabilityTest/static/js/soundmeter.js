'use strict';

jQuery.noConflict();
$ = jQuery;
var IDLE_TIMEOUT = 10; 
var _idleSecondsTimer = null;
var _idleCountTimer = null;
var soundlevel = 0;
var _idleSecondsCounter = 0;
var total_idle = 0;
var total_task_time = 0;

$('.toast').addClass('d-none');



function CountIdleTime(){
  if(soundlevel<0.1){
    total_idle++;
  }
}


class SoundMeter {
  constructor(context) {
    this.context = context;
    this.instant = 0.0;
    this.script = context.createScriptProcessor(2048, 1, 1);
    const that = this;
    _idleSecondsTimer = window.setInterval(CheckIdleTime, 1000);
    _idleCountTimer = window.setInterval(CountIdleTime,100);
    this.script.onaudioprocess = function (event) {
      const input = event.inputBuffer.getChannelData(0);
      let i;
      let sum = 0.0;
      for (i = 0; i < input.length; ++i) {
        sum += input[i] * input[i];
      }
      that.instant = Math.sqrt(sum / input.length);
      soundlevel = that.instant;

      if (soundlevel > 0.01) {
        console.log(soundlevel);
        _idleSecondsCounter = 0;
        $('.toast').addClass('d-none');
      }
    };
  }
  connectToSource(stream, callback) {
    console.log('SoundMeter connecting');
    try {
      this.mic = this.context.createMediaStreamSource(stream);
      this.mic.connect(this.script);
      // necessary to make sample run, but should not be.
      this.script.connect(this.context.destination);
      if (typeof callback !== 'undefined') {
        callback(null);
      }
    } catch (e) {
      console.error(e);
      if (typeof callback !== 'undefined') {
        callback(e);
      }
    }
  }
}


function CheckIdleTime() {
  _idleSecondsCounter++;
  total_task_time++;
  if (_idleSecondsCounter >= IDLE_TIMEOUT) {
      window.clearInterval(_idleSecondsTimer);
      $('.toast').removeClass('d-none')   
      $('.toast').toast('show');     
      _idleSecondsCounter = 0
      _idleSecondsTimer = window.setInterval(CheckIdleTime, 1000);    
  }
}

function StopIdleTimeCheck(){
  window.clearInterval(_idleSecondsTimer);
  window.clearInterval(_idleCountTimer);
  console.log(total_idle/10 + "_"+total_task_time);
  new Promise(UpdateTaskStatus);
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


async function UpdateTaskStatus(){

    var cookie = GetCookie('csrftoken');
    var answer = $("#taskq").val();
    var taskid = $("#taskid").val();
    var score = ((total_idle/11)/total_task_time)*100;
    var fd = new FormData();

    fd.append('taskq', answer);
    fd.append('taskid', taskid);
    fd.append('silence',score);
    fd.append('task_time',total_task_time);
    $.ajax({
      type: 'POST',
      url: '/statusupdate/',
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



