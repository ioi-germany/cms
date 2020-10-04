var __modal_opened = null;

function open_modal(s)
{
    if(__modal_opened != null) close_modal(__modal_opened);
    __modal_opened = s;

    var dialog = window.document.getElementById(s + "-dialog");

    dialog.classList.remove("hide");
    dialog.classList.add("in");

    document.getElementById("modal-backdrop").classList.remove("invisible");
}

function close_modal(s)
{
    var dialog = window.document.getElementById(s + "-dialog");

    dialog.classList.add("hide");
    dialog.classList.remove("in");

    document.getElementById("modal-backdrop").classList.add("invisible");
    __modal_opened = null;
}

function is_modal_opened()
{
    return __modal_opened != null;
}
