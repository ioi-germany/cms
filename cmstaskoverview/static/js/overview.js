function cell(t, entry)
{
    if(entry == "download")
    {
        return '<td class="download"><div class="download-icon" id = "download-' + t.code + '" data-code = "' + t.code + '"></div></td>';
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

function comp(a, b)
{
    if(a.code > b.code) return 1;
    if(a.code < b.code) return -1;
                        return 0;
}
                 
function fill_table(entries, desc, task_info, show_col, criteria)
{
    task_info = Array.sort(task_info, comp);

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
             
        if(t.old) table_body += '<tr>';         
        else table_body += '<tr class="new">';
        
        for(var j = 0; j < entries.length; ++j) 
            if(show_col[entries[j]])
                table_body += cell(t, entries[j]);
        table_body += '</tr>';
    }
                
    window.document.getElementById("overview").innerHTML = table_body;
    init_download_icons();
}
