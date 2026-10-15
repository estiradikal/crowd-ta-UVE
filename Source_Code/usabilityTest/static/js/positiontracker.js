'use strict';
$(document).ready(function () {



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

  function clickinformation(click_data) {
    var cookie = GetCookie('csrftoken');
    var taskid = $("#taskid").val();
    var date = new Date().toLocaleString().replace(',','');
    var click_info = "[button:'"+click_data+"',time:'"+date+"']";
    var fd = new FormData();

    fd.append('clickinfo', click_info);
    fd.append('taskid', taskid);
    $.ajax({
      type: 'POST',
      url: '/clickinfo/',
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

  function GetData(event){
    var obj = event.target;
    const info = obj.getAttribute('data-id');
    clickinformation(info);
  }
  $("#helpandinstructions span").on("click",GetData);
  $(".recorded-output").on("click",GetData);
  $("#recorded").on("click",GetData);
  $("button").on('click',GetData);
  $("#startrec").on('click',GetData);

});



  
  