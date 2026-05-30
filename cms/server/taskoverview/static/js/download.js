var __current_pdf = null;
var __pdf_jobs = {};
var __pdf_result = {};

function _pdf_mouse_down(e)
{
    __current_pdf = e.target;
    __current_pdf.classList.add("down");
}

function _pdf_mouse_up(e)
{
    if(__current_pdf != null)
    {
        __current_pdf.classList.remove("down");
        __current_pdf = null;
    }
}

function _compile(p, code, language)
{
    p.classList.remove("done");
    p.classList.remove("error");
    p.classList.add("loading");

    function init(s)
    {
        var handle = s.handle;

        function query()
        {
            function download(r)
            {
                if(r.done)
                {
                    if(!(code in __pdf_jobs)) return;

                    window.clearInterval(__pdf_jobs[code]);
                    delete __pdf_jobs[code];

                    __pdf_result[code] = r;

                    if(r.error)
                    {
                        p.classList.remove("loading");
                        p.classList.add("error");
                    }

                    else
                    {
                        p.classList.remove("loading");
                        p.classList.add("done");

                        let url = __url_root + "/download/" + code;
                        if (!!language)
                            url += "?language=" + language;
                        window.document.getElementById("fr-download-helper").src = url;
                    }
                }
            }

            $.get(__url_root + "/compile", { "code": code, "language": language, "handle": handle }, download);
        }

        __pdf_jobs[code] = window.setInterval(query, 500);
    }

    $.post(__url_root + "/compile", { "code": code, "language": language }, init);
}

function _pdf_mouse_click(e)
{
    var p = e.target;
    var code = p.dataset.code;
    var language = p.dataset.language;

    if(code in __pdf_result && __pdf_result[code].error)
    {
        window.document.getElementById("error-msg").srcdoc = __pdf_result[code].msg;
        window.document.getElementById("error-log").srcdoc = __pdf_result[code].log;
        window.document.getElementById("task-name").innerHTML = code;
        window.document.getElementById("retry-compilation").dataset.code = code;
        window.document.getElementById("retry-compilation").dataset.language = language;
        open_modal("error");
        return;
    }

    if(code in __pdf_jobs)  return;

    _compile(p, code, language);
}

function retry_compilation()
{
    var code = window.document.getElementById("retry-compilation").dataset.code;
    var language = window.document.getElementById("retry-compilation").dataset.language;
    delete __pdf_result[code];

    var p = window.document.getElementById("download-" + code);

    _compile(p, code, language);
    close_modal("error");
}

var __mouse_up_initialized = false;

function init_download_icons()
{
    if(!__mouse_up_initialized)
        window.addEventListener("mouseup", _pdf_mouse_up);
    __mouse_up_initialized = true;
}
