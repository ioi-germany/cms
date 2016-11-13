var __range_slider_currently_selected = null;
var __range_slider_last_position = {x: 0, y: 0};
var __curr_pos = 0;
var __range_slider_left = {};
var __range_slider_right = {};
var __range_slider_max = {};
var __range_slider_label = {};
var __internal_id = {};

var __RANGE_SLIDER_MARK_WIDTH = 14;
var __RANGE_SLIDER_MIN_DIST = 10;

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

function _is_left(o)
{
    return (o.id[o.id.length - 1] == 'l');
}

function _range_slider_max_pos(o)
{
    return _width(o.parentElement) - _width(o) - __RANGE_SLIDER_MARK_WIDTH - __RANGE_SLIDER_MIN_DIST;
}

function _base_id(id)
{
    return id.substring(0, id.length - 2);
}

function _update_range_label(o)
{
    var id = _base_id(o.id);

    if(__range_slider_label[id] != null)
    {
        __range_slider_label[id].children[0].innerHTML = __range_slider_left[id];
        __range_slider_label[id].children[2].innerHTML = __range_slider_right[id];
    }
}

function _update_range_slider(o)
{
    var id = _base_id(o.id);
    var left = _is_left(o);
    
    var b = window.document.getElementById(id + "_bar");
    var off = 0;
    if(!left)
        off = __RANGE_SLIDER_MARK_WIDTH + __RANGE_SLIDER_MIN_DIST;

    var raw = Math.max(0, Math.min(__curr_pos - off, _range_slider_max_pos(o)));
    
    if(left)
        __range_slider_left[id] = Math.min(Math.round(__range_slider_max[id] * (raw / _range_slider_max_pos(o))), __range_slider_right[id]);
    else
        __range_slider_right[id] = Math.max(Math.round(__range_slider_max[id] * (raw / _range_slider_max_pos(o))), __range_slider_left[id]);
}

function _snap_range_slider(o)
{
    var id = _base_id(o.id);
    var left = _is_left(o);

    var b = window.document.getElementById(id + "_bar");
    var p;
    if(left)
        p = __range_slider_left[id] * _range_slider_max_pos(o) / __range_slider_max[id];
    else
        p = __range_slider_right[id] * _range_slider_max_pos(o) / __range_slider_max[id] + __RANGE_SLIDER_MARK_WIDTH + __RANGE_SLIDER_MIN_DIST;
        
    o.style.left = p + "px"
    if(left) b.style.left = (p + .5 * _width(o)) + "px";
    else     b.style.right = (_width(o.parentElement) - p - .5 * _width(o)) + "px";
    _update_range_label(o);
}

function _range_slider_release()
{
    if(__range_slider_currently_selected != null)
    {
        __range_slider_currently_selected.classList.remove("down");
        _update_range_slider(__range_slider_currently_selected);
        _snap_range_slider(__range_slider_currently_selected);
        
    }

    __range_slider_currently_selected = null;
}

function _range_slider_mouse_down(e)
{
    _range_slider_release();
    __range_slider_currently_selected = e.target;
    __range_slider_currently_selected.classList.add("down");    
    __curr_pos = _relative_position(__range_slider_currently_selected).x;
    
    __range_slider_last_position.x = e.pageX;
    __range_slider_last_position.y = e.pageY;
}

function _range_slider_mouse_move(e)
{
    if(__range_slider_currently_selected != null)
    {
        var o = __range_slider_currently_selected; 
        
        __curr_pos += e.pageX - __range_slider_last_position.x;
        _update_range_slider(o);
        _snap_range_slider(o);
        
        __range_slider_last_position.x = e.pageX;
        __range_slider_last_position.y = e.pageY;
    }
}

function _range_slider_mouse_up(e)
{
    _range_slider_release();
}

function _range_slider_mouse_leave(e)
{
    _range_slider_release();
}

function init_range_sliders()
{
    var slider_labels = window.document.getElementsByClassName("range-slider-info");
    var slider_label_dict = {};
    
    for(var i = 0; i < slider_labels.length; ++i)
    {
        slider_labels[i].innerHTML =
            '<div class="range-slider-label-left unselectable"></div>' +
            '<div class="range-slider-label-center unselectable">&nbsp;&ndash;&nbsp;</div>' +
            '<div class="range-slider-label-right unselectable"></div>';
    
        slider_label_dict[slider_labels[i].dataset["for"]] = slider_labels[i];
    } 

    var sliders = window.document.getElementsByClassName("range-slider");
    
    for(var i = 0; i < sliders.length; ++i)
    {
        var id = "__range_slider_" + i;
    
        sliders[i].innerHTML = 
            '<div class="slider-helper">' + 
                '<div class="slider-outer">' +
                    '<div class="slider-helper">' +
                        '<div class="slider-bar" id = "' + id + '_bar">' + 
                        '</div>' +
                     '</div>' +
                '</div>' +
                '<div class="mark" id = "' + id + '_l"></div>' + 
                '<div class="mark" id = "' + id + '_r"></div>' +
            '</div>';
            
        __range_slider_left[id] = sliders[i].dataset.lower || 0;
        __range_slider_max[id] = sliders[i].dataset.maxval || 10;
        __range_slider_right[id] = sliders[i].dataset.upper || __range_slider_max[id];
        __range_slider_label[id] = slider_label_dict[sliders[i].id];
        
        __internal_id[sliders[i].id] = id;
        
        var l = window.document.getElementById(id + "_l");
        var r = window.document.getElementById(id + "_r");
        
        _snap_range_slider(l);   _snap_range_slider(r);
        _update_range_label(l);
        l.addEventListener("mousedown", _range_slider_mouse_down);
        r.addEventListener("mousedown", _range_slider_mouse_down);
    }
    
    window.addEventListener("mousemove", _range_slider_mouse_move);
    window.addEventListener("mouseup", _range_slider_mouse_up);
}

function range_slider_set(id, lower, upper)
{
    var i = __internal_id[id];
    var l = window.document.getElementById(i + "_l");
    var r = window.document.getElementById(i + "_r");
    
    __range_slider_left[i] = lower;
    __range_slider_right[i] = upper;
    
    _snap_range_slider(l); _snap_range_slider(r);
    _update_range_label(l);    
}

function range_slider_get_lower(id)
{
    return __range_slider_left[__internal_id[id]];
}

function range_slider_get_upper(id)
{
    return __range_slider_right[__internal_id[id]];
}

function range_slider_get(id)
{
    return { lower: range_slider_get_lower(id), upper: range_slider_get_upper(id) };
}
