'use strict';
$ = jQuery;



function copyText() {
    var copyTest = document.queryCommandSupported('copy');
    if (copyTest === true) {

        var copyText = document.getElementById("payId"); /* Get the text field */
        copyText.select();/* Select the text field */
        copyText.setSelectionRange(0, 99999); /*For mobile devices*/
        try {
            var successful = document.execCommand('copy');
            var msg = successful ? 'Copied!' : 'Whoops, not copied!';
            $(this).attr('data-original-title', msg).tooltip('show');
        } catch (err) {
            console.log('Oops, unable to copy');
        }

    } else {
        // if browser doesn't support execCommand('copy')
        window.prompt("Copy to clipboard: Press Ctrl+C ", $("#payId").val());
      }
}

$(document).ready(function () {

    $('[data-toggle="tooltip"]').tooltip();
    $("#button-copy").on('click', copyText);
    sessionStorage.clear();

});