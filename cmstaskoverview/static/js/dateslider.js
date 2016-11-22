var __date_slider_currently_selected = null;
var __date_slider_last_position = {x: 0, y: 0};
var __curr_pos = 0;
var __date_slider_val_raw = {};
var __date_slider_val = {}
var __date_slider_max = {};
var __date_slider_internal_id = {};
var __date_slider_stops = {};
var __date_slider_repr_val = {};
var __date_slider_reversed = {};
var __date_slider_external_id = {};
var __date_slider_last_scroll = 0;

function _relative_position(o)
{
    var r1 = o.getBoundingClientRect();
    var r2 = o.parentElement.getBoundingClientRect();
    
    return {x: r1.left - r2.left, y: r1.top - r2.top};
}

function _width(o)
{
    var r = o.getBoundingClientRect();
    return r.right - r.left;
}

function _height(o)
{
    var r = o.getBoundingClientRect();
    return Math.abs(r.bottom - r.top);
}

function _date_slider_max_pos(o)
{
    return _width(o.parentElement) - _width(o);
}

function _closest(allowed, found)
{
    var best = 0;
    
    for(var i = 1; i < allowed.length; ++i)
    {
        if(Math.abs(allowed[i] - found) < Math.abs(allowed[best] - found))
            best = i;
    }
    
    return best;
}

function _update_date_slider(o)
{
    __date_slider_val_raw[o.id] = Math.max(0, Math.min(__curr_pos, _date_slider_max_pos(o)));
    __date_slider_val[o.id] = _closest(__date_slider_stops[o.id], __date_slider_val_raw[o.id]);
}

function _snap_date_slider(o)
{
    var b = window.document.getElementById(o.id + "_bar");
    var p = __date_slider_stops[o.id][__date_slider_val[o.id]];

    o.style.left = p + "px"
    
    if(__date_slider_reversed[o.id])
    {
        b.style.left = (p + .5 * _width(o)) + "px";
    }
    
    else
    {
        b.style.right = (p + .5 * _width(o)) + "px";
    }
}

function _date_slider_release()
{
    if(__date_slider_currently_selected != null)
    {
        __date_slider_currently_selected.classList.remove("down");
        _update_date_slider(__date_slider_currently_selected);
        _snap_date_slider(__date_slider_currently_selected);
        
    }

    __date_slider_currently_selected = null;
}

function _date_slider_mouse_down(e)
{
    __date_slider_currently_selected = e.target;
    __date_slider_currently_selected.classList.add("down");    
    __curr_pos = _relative_position(__date_slider_currently_selected).x;
    __date_slider_last_position.x = e.pageX;
    __date_slider_last_position.y = e.pageY;
    
    __date_slider_last_scroll = window.document.getElementById(__date_slider_external_id[__date_slider_currently_selected.id]).scrollLeft;
}

function _date_slider_scroll()
{
    if(__date_slider_currently_selected != null)
    {
        var o = __date_slider_currently_selected; 
        var c = window.document.getElementById(__date_slider_external_id[o.id]);
        
        __curr_pos += c.scrollLeft - __date_slider_last_scroll;
        _update_date_slider(o);
        _snap_date_slider(o);
        
        __date_slider_last_scroll = c.scrollLeft;
    }
}

function _date_slider_mouse_move(e)
{
    if(__date_slider_currently_selected != null)
    {   
        var o = __date_slider_currently_selected; 
        var c = window.document.getElementById(__date_slider_external_id[o.id]);
        
        __curr_pos += e.pageX - __date_slider_last_position.x;
        _update_date_slider(o);
        _snap_date_slider(o);
        
        __date_slider_last_position.x = e.pageX;
        __date_slider_last_position.y = e.pageY;
    }
}

function _date_slider_mouse_up(e)
{
    _date_slider_release();
}

function _date_slider_mouse_leave(e)
{
    _date_slider_release();
}

function _date_slider_click(e, id)
{
    var o = window.document.getElementById(id);
    var c = window.document.getElementById(__date_slider_external_id[id]);

    __date_slider_currently_selected = o;
    var x = c.getBoundingClientRect().x || c.getBoundingClientRect().left
    __curr_pos = e.pageX - x + c.scrollLeft;

    _update_date_slider(o);
    _snap_date_slider(o);
    _date_slider_release();
}

function _tag(color, label, off, id)
{
    off -= 10; // half tag-height

    var result = 
        '<div class = "tag ' + color + '" style="top:' + off + 'px;">' +
            '<div class = "tag-body" id = "' + id + '">' +
                '<label class="tag-label">' +
                    label +
                '</label>' +
            '</div>' +
            '<div class="tip">' +
            '</div>' + 
        '</div>';
    return result;
}

var __date_slider_globally_initialized = false;

function init_date_slider(id, data, reversed)
{
    var s = window.document.getElementById(id);
    var id_internal = id + "__internal";
    
    var t = [0];
    var l = 0;    
    for(var i = 1; i < data.length; ++i)
    {
        var delta = Math.sqrt(data[i].timestamp - data[i - 1].timestamp);
        t[t.length] = t[t.length - 1] + delta;
        l += delta;
    }
    
    var outer = 30;
    var mark_width = 16;
    var w = _width(s);
    
    var factor = (w - 2 * outer - mark_width) / l;

    for(var i = 0; i < t.length; ++i)
        t[i] = t[i] * factor;
    
    var MIN_DIST = 30;
    var MAX_STRETCH_FACTOR = 1.75;
    factor = 1;
    
    for(var i = 1; i < t.length; ++i)
        factor = Math.max(factor, MIN_DIST / (t[i] - t[i - 1]));
    factor = Math.min(factor, MAX_STRETCH_FACTOR);
    for(var i = 0; i < t.length; ++i)
        t[i] = Math.floor(t[i] * factor);
    
    
    var u = [t[0]];    
    
    var off = 0;
    
    for(var i = 1; i < t.length; ++i)
    {
        if(t[i] - t[i - 1] < MIN_DIST)
            off += MIN_DIST - (t[i] - t[i - 1]);
        
        u[i] = t[i] + off;
    }
    
    t = u;
    
    w = Math.max(w, t[t.length - 1] + outer + mark_width);
    
    var colors = ["red", "blue", "green"];
    var tags = "";
    for(var i = 0; i < data.length; ++i)
        tags += _tag(colors[i % colors.length], data[i].info, t[i] + outer, id_internal + "_tag_" + i);

    var d = [0];    
    for(var i = 1; i < t.length; ++i)
        d[i] = Math.round(.5 * (t[i - 1] + t[i])) + outer - .5 * mark_width;
    d[d.length] = w - mark_width;
    
    __date_slider_stops[id_internal] = d;
        
    s.innerHTML = 
        '<div class="slider-helper" id = "' + id_internal + '_helper">' + 
            '<div class="slider-outer">' +
                '<div class="slider-helper">' +
                    '<div class="slider-bar" id = "' + id_internal + '_bar">' + 
                    '</div>' +
                '</div>' +
            '</div>' +
            '<div class="mark" id = "' + id_internal + '"></div>' + 
        '</div>' +
        '<div class="ds-annotation-container" id = "' + id_internal + '_ac">' +
            '<div class="ds-annotations" id="' + id_internal + '_annotations">' +
                tags +
            '</div>' +
        '</div>';
          
    document.getElementById(id_internal + "_helper").style.width = w + "px";
    s.scrollLeft = s.scrollWidth;
          
          
    var w = 0;
          
    for(var i = 0; i < data.length; ++i)
        w = Math.max(w, _width(window.document.getElementById(id_internal + "_tag_" + i)));
            
    window.document.getElementById(id_internal + "_ac").style.height = (w + 15) + "px";          
      
    if(reversed)
    {
        __date_slider_val[id_internal] = d.length - 1;
        __date_slider_val_raw[id_internal] = d[d.length - 1];
    }
    
    else
    {        
        __date_slider_val_raw[id_internal] = 0;
        __date_slider_val[id_internal] = 0;
    }            
    
    __date_slider_reversed[id_internal] = reversed;
    
    __date_slider_internal_id[id] = id_internal;
    __date_slider_external_id[id_internal] = id;
        
    __date_slider_repr_val[id_internal] = [data[0].timestamp - 1];
    for(var i = 0; i < data.length; ++i)
        __date_slider_repr_val[id_internal][i + 1] = data[i].timestamp;
        
    var o = window.document.getElementById(id_internal);
        
    _snap_date_slider(o);
    
    o.addEventListener("mousedown", _date_slider_mouse_down);
    s.addEventListener("scroll", _date_slider_scroll);    
    s.addEventListener("click", function(e) { _date_slider_click(e, id_internal); });
        
    var a = window.document.getElementById(id_internal + '_annotations');
    var w = _width(a);
    var h = _height(a);
        
    a.style.transform = "rotate(-90deg)";
    a.style.left = ((h - w) / 2) + "px";
    a.style.top =  ((w - h) / 2) + "px";      
    
    if(__date_slider_globally_initialized)
    {
        window.addEventListener("mousemove", _date_slider_mouse_move);
        window.addEventListener("mouseup", _date_slider_mouse_up);
    }
    
    __date_slider_globally_initialized = true;
}

function date_slider_get_raw(id)
{
    return __date_slider_val[__date_slider_internal_id[id]];
}

function date_slider_get_val(id)
{
    return __date_slider_repr_val[__date_slider_internal_id[id]][date_slider_get_raw(id)];
}

function date_slider_set(id, val)
{
    var ii = __date_slider_internal_id[id];
    __date_slider_val[ii] = _closest(__date_slider_repr_val[ii], val);
    _snap_date_slider(window.document.getElementById(ii));
}
