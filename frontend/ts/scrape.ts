/// <reference path="jquery.d.ts" />

declare var ace: any;

$(()=> {
    var editor = ace.edit("editor");
    editor.setTheme("ace/theme/monokai");
    editor.getSession().setMode("ace/mode/python");

    $("#execute").click(()=> {
	var url = $("#url").val();
	if (url.indexOf("http://") != 0 && url.indexOf("https://") != 0) {
	    $("#url").focus();
	    return;
	}
	$("#result").html("");
	$("#execute").attr("disabled", true);
	var script = editor.getSession().getValue();
	$.post("scrape", {url:$("#url").val(), script:script}, (data)=>{
	    $("#result").html(data.html);
	    $("#execute").attr("disabled", false);
	    $("#execute").removeAttr("disabled");
	});
    });
});