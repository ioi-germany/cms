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
             
                        window.location.href = "/download/" + code;
                    }
                }
            }
        
            $.get("/compile", { "code": code, "handle": handle }, download);
        }
        
        __pdf_jobs[code] = window.setInterval(query, 500);
    }
    
    $.post("/compile", { "code": code }, init);             
}
         
function _pdf_mouse_click(e)
{
    var p = e.target;
    var code = p.dataset.code;
    
    if(code in __pdf_result && __pdf_result[code].error)
    {
        window.document.getElementById("error-msg").innerHTML = __pdf_result[code].msg;
        window.document.getElementById("error-log").innerHTML = __pdf_result[code].log;
        window.document.getElementById("task-name").innerHTML = code;
        window.document.getElementById("retry-compilation").dataset.code = code;
        open_modal("error");
        return;
    }
    
    if(code in __pdf_jobs)  return;
    
    _compile(p, code);
}

function retry_compilation()
{
    var code = window.document.getElementById("retry-compilation").dataset.code;
    delete __pdf_result[code];
    
    var p = window.document.getElementById("download-" + code);
    
    _compile(p, code);    
    close_modal("error");
}

function init_download_icons()
{
    var d = document.getElementsByClassName("download-icon");

    for(var i = 0; i < d.length; ++i)
    {
        d[i].addEventListener("mousedown", _pdf_mouse_down);
        d[i].addEventListener("click", _pdf_mouse_click);
    }
                
    window.addEventListener("mouseup", _pdf_mouse_up);
}
