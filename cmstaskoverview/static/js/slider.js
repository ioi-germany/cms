var __slider_currently_selected = null;
var __slider_last_position = {x: 0, y: 0};
var __curr_pos = 0;
var __slider_val_raw = {};
var __slider_val = {}
var __slider_max = {};
var __slider_label = {};
var __internal_id = {};

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

function _slider_max_pos(o)
{
    return _width(o.parentElement) - _width(o);
}

function _update_label(o)
{
    if(__slider_label[o.id] != null)
    {
        __slider_label[o.id].innerHTML = __slider_val[o.id];
    }
}

function _update_slider(o)
{
    var b = window.document.getElementById(o.id + "_bar");

    __slider_val_raw[o.id] = Math.max(0, Math.min(__curr_pos, _slider_max_pos(o)));
    o.style.left = __slider_val_raw[o.id] + "px";
    b.style.width = (__slider_val_raw[o.id] + .5 * _width(o)) + "px";
    
    __slider_val[o.id] = Math.round(__slider_max[o.id] * (__slider_val_raw[o.id] / _slider_max_pos(o)));
    
    _update_label(o);
}

function _snap_slider(o)
{
    var b = window.document.getElementById(o.id + "_bar");
    var p = __slider_val[o.id] * _slider_max_pos(o) / __slider_max[o.id];
    
    o.style.left = p + "px"
    b.style.width = (p + .5 * _width(o)) + "px";
}

function _slider_release()
{
    if(__slider_currently_selected != null)
    {
        __slider_currently_selected.classList.remove("down");
        _update_slider(__slider_currently_selected);
        _snap_slider(__slider_currently_selected);
        
    }

    __slider_currently_selected = null;
}

function _slider_mouse_down(e)
{
    __slider_currently_selected = e.target;
    __slider_currently_selected.classList.add("down");    
    __curr_pos = _relative_position(__slider_currently_selected).x;
    __slider_last_position.x = e.pageX;
    __slider_last_position.y = e.pageY;
}

function _slider_mouse_move(e)
{
    if(__slider_currently_selected != null)
    {
        var o = __slider_currently_selected; 
        
        __curr_pos += e.pageX - __slider_last_position.x;
        _update_slider(o);
        _snap_slider(o);
        
        __slider_last_position.x = e.pageX;
        __slider_last_position.y = e.pageY;
    }
}

function _slider_mouse_up(e)
{
    _slider_release();
}

function _slider_mouse_leave(e)
{
    _slider_release();
}

function _init_sliders()
{
    var slider_labels = window.document.getElementsByClassName("slider-info");
    var slider_label_dict = {};
    
    for(var i = 0; i < slider_labels.length; ++i)
    {
        slider_label_dict[slider_labels[i].dataset["for"]] = slider_labels[i];
    } 

    var sliders = window.document.getElementsByClassName("slider");
    
    for(var i = 0; i < sliders.length; ++i)
    {
        var id = "__slider_" + i;
    
        sliders[i].innerHTML = 
            '<div class="slider-helper">' + 
                '<div class="slider-outer">' +
                    '<div class="slider-helper">' +
                        '<div class="slider-bar" id = "' + id + '_bar">' + 
                        '</div>' +
                     '</div>' +
                '</div>' +
                '<div class="mark" id = "' + id + '"></div>' + 
            '</div>';
            
        __slider_val_raw[id] = 0;
        __slider_val[id] = sliders[i].dataset.val || 0;
        __slider_max[id] = sliders[i].dataset.maxval || 10;
        __slider_label[id] = slider_label_dict[sliders[i].id];
        
        __internal_id[sliders[i].id] = id;
        
        var o = window.document.getElementById(id);
        
        _snap_slider(o);
        _update_label(o);
        o.addEventListener("mousedown", _slider_mouse_down);
    }
    
    window.addEventListener("mousemove", _slider_mouse_move);
    window.addEventListener("mouseup", _slider_mouse_up);
}

window.addEventListener("load", _init_sliders);

function get_slider_val(id)
{
    return __slider_val[__internal_id[id]];
}
