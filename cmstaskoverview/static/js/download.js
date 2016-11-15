var __current_pdf = null;
var __pdf_jobs = {};
            
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

function _download_file(r)
{
    alert(r);
}
            
function _pdf_mouse_click(e)
{
    var p = e.target;
    var code = p.dataset.code;
    
    if(code in __pdf_jobs)  return;
    
    p.classList.remove("done");
    p.classList.remove("error");
    p.classList.add("loading");
    
    $.post("/compile", { "code": code });
             
    function query()
    {
        function handle(r)
        {        
            if(r.done)
            {
                window.clearInterval(__pdf_jobs[code]);
                delete __pdf_jobs[code];
                
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
    
        $.get("/compile", { "code": code }, handle);
    }
             
    __pdf_jobs[code] = window.setInterval(query, 1500);
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
