var __current_download = null;
var __pdf_jobs = {};
var __pdf_result = {};

function _download_mouse_down(e)
{
    __current_download = e.target;
    __current_download.classList.add("down");
}

function _download_mouse_up(e)
{
    if(__current_download != null)
    {
        __current_download.classList.remove("down");
        __current_download = null;
    }
}

function _compile(p, code)
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

                        window.document.getElementById("fr-download-helper").src = __url_root + "/pdf/" + code;
                    }
                }
            }

            $.get(__url_root + "/compile", { "code": code, "handle": handle }, download);
        }

        __pdf_jobs[code] = window.setInterval(query, 500);
    }

    $.post(__url_root + "/compile", { "code": code }, init);
}

function _yield(p, code)
{
    p.classList.remove("done");
    p.classList.remove("error");
    p.classList.add("loading");

    p.classList.remove("loading");
    p.classList.add("done");

    window.document.getElementById("fr-download-helper").src = __url_root + "/tex/" + code;
}

function _download_mouse_click(e)
{
    var p = e.target;

    var code = p.dataset.code;
    if(p.id.startsWith("pdf")){
        if(code in __pdf_result && __pdf_result[code].error)
        {
            window.document.getElementById("error-msg").textContent = __pdf_result[code].msg;
            window.document.getElementById("error-log").textContent = __pdf_result[code].log;
            window.document.getElementById("task-name").innerHTML = code;
            window.document.getElementById("retry-compilation").dataset.code = code;
            open_modal("error");
            return;
        }

        if(code in __pdf_jobs)  return;

        _compile(p, code);
    }
    else{
        _yield(p,code);
    }
}

function retry_compilation()
{
    var code = window.document.getElementById("retry-compilation").dataset.code;
    delete __pdf_result[code];

    var p = window.document.getElementById("pdf-" + code);

    _compile(p, code);
    close_modal("error");
}

var __mouse_up_initialized = false;

function init_download_icon(task, pdf=true, lan=null)
{
    var extended_code = (pdf?"pdf-":"tex-") + task + (lan!=null?("-"+lan):"");
    var d = window.document.getElementById( extended_code );

    if(d==null) return;

    d.addEventListener("mousedown", _download_mouse_down);
    d.addEventListener("click", _download_mouse_click);

    if(!__mouse_up_initialized)
        window.addEventListener("mouseup", _download_mouse_up);
    __mouse_up_initialized = true;
}

function init_upload_icon(task, lan=null)
{
    //TODO Init here instead of embedded in HTML
}
