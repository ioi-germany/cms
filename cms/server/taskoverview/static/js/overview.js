function inner_cell(t, entry)
{
    if(entry == "download")
    {
        return '<div class="download-icon" id = "download-' + t.code + '" data-code = "' + t.code + '"></div>';
    }
    
    if(entry == "keywords")
    { 
        var r = '<ul class="embedded">';
        if(t[entry].length == 0) r += "&mdash;";
                    
        for(var i = 0; i < t[entry].length; ++i)
            r += '<li>' + t[entry][i] + '</li>';
        r += '</ul>';
        return r;
    }
    
    if(entry == "uses")
    {
        var r = '<ul class="embedded">';
        if(t[entry].length == 0) r += "&mdash;";
                    
        for(var i = 0; i < t[entry].length; ++i)
            r += '<li>' + t[entry][i].info + '</li>';
        r += '</ul>';
        return r;
    }
    
    else
    {
        return t[entry]
    }
}

function cell(t, entry)
{
    var id = "cell-" + t.code + "-" + entry;

    if(entry == "download")
    {
        return '<td id = "' + id + '" class="download">' + inner_cell(t, entry) +'</td>';
    }

    else
    {
        return '<td id = "' + id + '">' + inner_cell(t, entry) + '</td>';
    }
}

function inner_error_cell(t)
{
    if("error" in t) return "<b>ERROR!</b> " + t.error;
    return "";
}

function error_cell(t)
{
    var id = "cell-" + t.code + "-error-msg";
    return '<td id="' + id + '" class="error-msg">' + inner_error_cell(t) + '</td>';
}

function relevant(t, c)
{
    if("error" in t) return true;

    uses_ok = true;
    
    for(var i = 0; i < t.uses.length; ++i)
        if(t.uses[i].timestamp > criteria.only_before)
            uses_ok = false;

    return t.algorithm <= c.alg_diff.upper && t.algorithm >= c.alg_diff.lower &&
           t.implementation <= c.impl_diff.upper && t.implementation >= c.impl_diff.lower &&
           (c.show_public || !t["public"]) && (c.show_private || t["public"]) &&
           uses_ok;
}


var __info = {};
var __tasks = [];
var __task_dict = {};
var __removed = {};
            
function build_row(task_code)
{
    var t = __info[task_code];
    var r = "";
    
    r += '<tr id = "row-' + t.code + '">';  
    r += cell(t, entries[0]);
    r += error_cell(t);
    
    for(var j = 1; j < entries.length; ++j) 
            r += cell(t, entries[j]);
    r += '</tr>';
    
    return r;
}
                 
function fill_table(new_tasks, updated_tasks, show_col, criteria, init)
{
    new_tasks = new_tasks.sort();
    
    if(init)
    {
        var table_body = "";
                
        table_body += '<tr id="overview-heading" class="odd">';
        for(var j = 0; j < entries.length; ++j)
            if(entries[j] == "download")
                table_body += '<td id="overview-heading-' + entries[j] + '" class="th download-heading">' + desc[entries[j]] + '</td>'; // table-bordered doesn't work with th, so we emulate it
            else
                table_body += '<td id="overview-heading-' + entries[j] + '" class="th">' + desc[entries[j]] + '</td>'; // table-bordered doesn't work with th, so we emulate it
        table_body += '</tr>'; 
        window.document.getElementById("overview").innerHTML = table_body;
    }
    
    function make_class_removal_function(id, cl)
    {
        return function() { window.document.getElementById(id).classList.remove(cl); }
    }
    
    // Insert new rows (à la mergesort)
    var last_entry = "overview-heading";
    var old_tasks_idx = 0, new_tasks_idx = 0;
    
    while(true)
    {
        if(old_tasks_idx >= __tasks.length && new_tasks_idx >= new_tasks.length) break;
        
        if(old_tasks_idx >= __tasks.length || __tasks[old_tasks_idx] >= new_tasks[new_tasks_idx])
        {
            $(build_row(new_tasks[new_tasks_idx], show_col)).insertAfter("#" + last_entry);
            init_download_icon(new_tasks[new_tasks_idx])
            last_entry = "row-" + new_tasks[new_tasks_idx];
            
            if(!init)
            {
                window.document.getElementById(last_entry).classList.add("fresh");
                // We need to remove the attribute after the animation is done for other animations to be triggered -- moreover, it is semantically nicer
                window.document.getElementById(last_entry).addEventListener("animationend", make_class_removal_function(last_entry, "fresh"));
                
            }
            
            ++new_tasks_idx;
        }
        
        else
        {
            last_entry = "row-" + __tasks[old_tasks_idx];
            ++old_tasks_idx;
        }
    }
    
    __tasks = __tasks.concat(new_tasks).sort();
    
    var num_interesting_columns = 0;
    for(var j = 1; j < entries.length - 1; ++j)
        if(show_col[entries[j]]) ++num_interesting_columns;
    
    for(var i = 0; i < __tasks.length; ++i)
    {
        // Apply row selection
        var id = "row-" + __tasks[i];
        var row = window.document.getElementById(id);
    
        if(relevant(__info[__tasks[i]], criteria))
            row.classList.remove("hidden");
        else
            row.classList.add("hidden");
            
        // Remove tasks that are no longer available
        if(__tasks[i] in __removed)
        {
            row.classList.add("removed");
            
            // Indirectness needed to make currying work
            function make_removal_function(s)
            {
                return function() { $("#" + s).remove(); }
            }
            
            window.setTimeout(make_removal_function("row-" + __tasks[i]), 1000);
        }
        
        // Highlight unused tasks
        if(__info[__tasks[i]].old || "error" in __info[__tasks[i]])
            row.classList.remove("new");
        else
            row.classList.add("new");
            
        // Apply column selection        
        for(var j = 0; j < entries.length; ++j)
        {
            var cell = window.document.getElementById("cell-" + __tasks[i] + "-" + entries[j]);
        
            if(show_col[entries[j]])
                cell.classList.remove("hidden");
            else
                cell.classList.add("hidden");
        }
        
        window.document.getElementById("cell-" + __tasks[i] + "-error-msg").colSpan = num_interesting_columns;
        
        // Error or correct entry?
        var t = __info[__tasks[i]];
        
        if("error" in t)
        {
            for(var j = 1; j < entries.length - 1; ++j)
            {
                var cell = window.document.getElementById("cell-" + __tasks[i] + "-" + entries[j]);
                cell.classList.add("hidden");
            }    
            
            window.document.getElementById("cell-" + __tasks[i] + "-error-msg").classList.remove("no-error");           
        }
        
        else
        {
            window.document.getElementById("cell-" + __tasks[i] + "-error-msg").classList.add("no-error");       
        }
    }
    
    // Update tasks that changed since last query
    for(var i = 0; i < updated_tasks.length; ++i)
    {
        var row = window.document.getElementById("row-" + updated_tasks[i]);
        
        for(var j = 0; j < entries.length; ++j)
        {
            if(entries[j] == "download") continue;
            
            var cell = window.document.getElementById("cell-" + updated_tasks[i] + "-" + entries[j]);
        
            cell.innerHTML = inner_cell(__info[updated_tasks[i]], entries[j]);
        
            /*if(show_col[entries[j]])
                cell.classList.remove("hidden");
            else
                cell.classList.add("hidden");*/
        }
        
        window.document.getElementById("cell-" + updated_tasks[i] + "-error-msg").innerHTML = inner_error_cell(__info[updated_tasks[i]]);
        
        row.classList.add("updated");
        window.setTimeout(make_class_removal_function("row-" + updated_tasks[i], "updated"), 1000);
    }
    
    // Remove tasks that have been deleted from the filesystem
    var __tasks_backup = __tasks;
    __tasks = [];
    for(var i = 0; i < __tasks_backup.length; ++i)
    {
        if((__tasks_backup[i] in __removed))
            delete __task_dict[__tasks_backup[i]];
        else
            __tasks.push(__tasks_backup[i]);
    }
   
    for(var j = 0; j < entries.length; ++j)
    {
        var cell = window.document.getElementById("overview-heading-" + entries[j]);
        
        if(show_col[entries[j]])
            cell.classList.remove("hidden");
        else
            cell.classList.add("hidden");     
    }
    
    // Coloring and rounded borders
    var count = 0;
    var prefix = "overview-heading";
    
    for(var j = 0; j < entries.length; ++j)
    {
        var id = prefix + "-" + entries[j];
        var cell = window.document.getElementById(id);
        cell.classList.remove("lower-left");
        cell.classList.remove("lower-right");
        cell.classList.remove("upper-left");
        cell.classList.remove("upper-right");
    }
    
    for(var i = 0; i < __tasks.length; ++i)
    {
        var id = "row-" + __tasks[i];
        var row = window.document.getElementById(id);
        
        if(row.classList.contains("hidden")) continue;
        
        if(count % 2 == 0) row.classList.remove("odd");
        else               row.classList.add("odd");
        
        ++count;
        prefix = "cell-" + __tasks[i];
        
        for(var j = 0; j < entries.length; ++j)
        {
            var id = prefix + "-" + entries[j];
            var cell = window.document.getElementById(id);
            cell.classList.remove("lower-left");
            cell.classList.remove("lower-right");
            cell.classList.remove("upper-left");
            cell.classList.remove("upper-right");
        }
    }
    
    var first_col = null;
    var last_col = null;
    
    for(var j = 0; j < entries.length; ++j)
    {
        var id = prefix + "-" + entries[j];
        var cell = window.document.getElementById(id);
            
        if(cell.classList.contains("hidden")) continue;
            
        if(first_col == null) first_col = entries[j];
        last_col = entries[j];
    }
        
    if(last_col != null)
    {
        window.document.getElementById(prefix + "-" + first_col).classList.add("lower-left");
        window.document.getElementById(prefix + "-" + last_col).classList.add("lower-right");
        
        window.document.getElementById("overview-heading-" + first_col).classList.add("upper-left");
        window.document.getElementById("overview-heading-" + last_col).classList.add("upper-right");
    }
    
    // Create overview of problematic info.json files
    var json_issues = [];
    
    for(var i = 0; i < __tasks.length; ++i)
        if("error" in __info[__tasks[i]])
            json_issues.push(__tasks[i]);
    
    if(json_issues.length == 0)
        window.document.getElementById("json-errors").classList.add("no-errors");
    
    else
        window.document.getElementById("json-errors").classList.remove("no-errors");
        
    window.document.getElementById("tasks-with-issues").innerHTML = json_issues.join(", ");
}

function update(init=false, sliders=false)
{
    function on_list(l)
    {
        var response = JSON.parse(l);
        
        var available_tasks = [];
        var available_tasks_dict = {};
        for(var i = 0; i < response.length; ++i)
        {
            available_tasks.push(response[i].task);
            available_tasks_dict[response[i].task] = response[i].timestamp;
        }
        
        var new_tasks = [];
        var updated_tasks = [];
        
        for(var i = 0; i < available_tasks.length; ++i)
        {
            var t = available_tasks[i];
        
            if(!(t in __task_dict))
            {
                new_tasks.push(t);
                __task_dict[t] = available_tasks_dict[t];
            }
            
            if(__task_dict[t] < available_tasks_dict[t])
            {
                updated_tasks.push(t);
                __task_dict[t] = available_tasks_dict[t];
            }
        }

        __removed = {};
        
        for(var i = 0; i < __tasks.length; ++i)
            if(!(__tasks[i] in available_tasks_dict))
                __removed[__tasks[i]] = true;
    
        function on_info(i)
        {
            var info = JSON.parse(i);
            for(var i = 0; i < new_tasks.length; ++i)
                __info[new_tasks[i]] = info[new_tasks[i]];
            for(var i = 0; i < updated_tasks.length; ++i)
                __info[updated_tasks[i]] = info[updated_tasks[i]];
            
            fill_table(new_tasks, updated_tasks, show_col, criteria, init);
            if(sliders) update_sliders(init);
        }
    
        if(new_tasks.length > 0 || updated_tasks.length > 0)
        {
            $.get(__url_root + "/info", {"tasks": JSON.stringify(new_tasks.concat(updated_tasks))}, on_info);
        }
        
        else
        {
            fill_table(new_tasks, updated_tasks, show_col, criteria, init);
            if(sliders) update_sliders(init);
        }
    }

    $.get(__url_root + "/list", "", on_list);
}

function update_sliders(init=false)
{
    init_date_slider("uses", interesting_dates(), true);
    if(!init) date_slider_set("uses", criteria.only_before); 
    if(init) criteria.only_before = date_slider_get_val("uses"); 
}

function interesting_dates()
{
    var raw = [];
    
    for(var i = 0; i < __tasks.length; ++i)
        raw = raw.concat(__info[__tasks[i]].uses);
    
    function my_comp(a, b)
    {
        if(a.timestamp < b.timestamp) return -1;
        if(a.timestamp > b.timestamp) return 1;
        return 0;
    }
    
    raw = raw.sort(my_comp);

    /* Merge multiple entries for the same contest (multiple days,
       typos in the files etc.):
      
       If there are multiple entries with the same description at successive
       time points, we keep only the last one.
       
       This is of course not perfect, but it should work in most cases.
       Since the selection criteria are just for convenience, this should
       be fine (and it is certainly much better than having to sanitize all
       info.json files by hand)
     */
    var dates = [];
     
    for(var i = 0; i < raw.length; ++i)
    {
        if(dates.length > 0 && dates[dates.length - 1].info == raw[i].info)
            dates.pop();
        dates.push(raw[i]);
    }

    return dates;
}
