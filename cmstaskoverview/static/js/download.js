var __current_pdf = null;
            
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
            
function _pdf_mouse_click(e)
{
    var p = e.target;
    p.classList.remove("down");
    p.classList.add("loading");
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
