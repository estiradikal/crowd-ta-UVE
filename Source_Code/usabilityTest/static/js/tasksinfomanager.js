'use strict';

jQuery.noConflict();
$ = jQuery;


var currntTask = $("#taskid").val();
var totaltask = $("#totaltasks").val();
var nextTask = currntTask*1+1;
var nextUrl = "/test/"+nextTask;

if(currntTask*1<totaltask*1){
    $('#goToNextTask span').text('Next Task');
    $('#goToNextTask').attr('href', nextUrl);
}else{
    $('#goToNextTask span').text('Finish');
    $("#goToNextTask").attr('href', "/payId/");
}





