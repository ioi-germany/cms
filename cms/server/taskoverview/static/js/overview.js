var __info = {};
var __tasks = [];
var __task_dict = {};

function parse_info(info)
{
    if ("folder" in info) {
        info["tags"] ??= [];
        info["tags"].push(info["folder"].replace(/^tasks[-_/]?/i, ""));
        delete info["folder"];
    }
    for (const k of ["keywords", "tags"]) {
        info[k] ??= [];
        info[k] = info[k]
            .map(tag => tag.trim().toUpperCase())
            .filter(tag => tag.length > 0);
    }
    return info;
}

function init_table(tasks, info)
{
    for(var i = 0; i < tasks.length; ++i)
    {
        var t = tasks[i].task;
        __task_dict[t] = tasks[i].timestamp;
        __info[t] = parse_info(info[t]);
    }
    fill_table(tasks.map((t) => t.task), [], {}, show_col, criteria, true);
    update_sliders(true);
}

function fill_table(new_tasks, updated_tasks, removed_tasks, show_col, criteria, init)
{
    for(var t of Object.keys(removed_tasks))
        delete __task_dict[t];
    __tasks = __tasks.filter((t) => !(t in removed_tasks)).concat(new_tasks).sort();
    if (window.updateTaskRows)
        window.updateTaskRows(new_tasks, updated_tasks, removed_tasks, show_col, criteria, init);
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

        var removed_tasks = {};

        for(var i = 0; i < __tasks.length; ++i)
            if(!(__tasks[i] in available_tasks_dict))
                removed_tasks[__tasks[i]] = true;

        function on_info(i)
        {
            var info = JSON.parse(i);
            for(var i = 0; i < new_tasks.length; ++i)
                __info[new_tasks[i]] = parse_info(info[new_tasks[i]]);
            for(var i = 0; i < updated_tasks.length; ++i)
                __info[updated_tasks[i]] = parse_info(info[updated_tasks[i]]);

            fill_table(new_tasks, updated_tasks, removed_tasks, show_col, null, init);
            if(sliders) update_sliders(init);
        }

        if(new_tasks.length > 0 || updated_tasks.length > 0)
        {
            $.get(__url_root + "/info", {"tasks": JSON.stringify(new_tasks.concat(updated_tasks))}, on_info);
        }

        else
        {
            fill_table(new_tasks, updated_tasks, removed_tasks, show_col, null, init);
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
