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

function cell(t, entry)
{
    if(entry == "download")
    {
        return '<td class="download"><div class="download-icon" data-code = "' + t.code + '"></div></td>';
    }

    if(entry == "keywords")
    {
        var r = '<ul class="embedded">';
        if(t[entry].length == 0) r += "&mdash;";
                    
        for(var i = 0; i < t[entry].length; ++i)
            r += '<li>' + t[entry][i] + '</li>';
        r += '</ul>';
        return '<td>' + r + '</td>';
    }
                
    if(entry == "uses")
    {
        var r = '<ul class="embedded">';
        if(t[entry].length == 0) r += "&mdash;";
                    
        for(var i = 0; i < t[entry].length; ++i)
            r += '<li>' + t[entry][i].info + '</li>';
        r += '</ul>';
        return '<td>' + r + '</td>';
    }

    else
    {
        return '<td>' + t[entry] + '</td>';
    }
}

function relevant(t, c)
{
    uses_ok = true;
    
    for(var i = 0; i < t.uses.length; ++i)
        if(t.uses[i].timestamp > criteria.only_before)
            uses_ok = false;

    return t.algorithm <= c.alg_diff.upper && t.algorithm >= c.alg_diff.lower &&
           t.implementation <= c.impl_diff.upper && t.implementation >= c.impl_diff.lower &&
           (c.show_public || !t["public"]) && (c.show_private || t["public"]) &&
           uses_ok;
}
                 
function fill_table(entries, desc, task_info, show_col, criteria)
{
    var table_body = "";
                
    table_body += '<tr>';
    for(var j = 0; j < entries.length; ++j)
        if(show_col[entries[j]])
            table_body += '<td class="th">' + desc[entries[j]] + '</td>'; // table-bordered doesn't work with th, so we emulate it
    table_body += '</tr>';
                
    for(var i = 0; i < task_info.length; ++i)
    {
        var t = task_info[i];
        if(!relevant(t, criteria)) continue;
                    
        table_body += '<tr>';
        for(var j = 0; j < entries.length; ++j) 
            if(show_col[entries[j]])
                table_body += cell(t, entries[j]);
        table_body += '</tr>';
    }
                
    window.document.getElementById("overview").innerHTML = table_body;
    init_download_icons();
}
