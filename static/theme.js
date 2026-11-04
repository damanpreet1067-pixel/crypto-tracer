(function () {
    var KEY = "ct-theme";
    var DEFAULT = "light";            // change to "dark" to start in dark mode
    var root = document.documentElement;

    function read() {
        try { return localStorage.getItem(KEY); } catch (e) { return null; }
    }
    function write(value) {
        try { localStorage.setItem(KEY, value); } catch (e) {}
    }
    function apply(theme) {
        root.setAttribute("data-theme", theme);
        var button = document.getElementById("theme-toggle");
        if (button) {
            button.textContent = theme === "dark" ? "\u2600" : "\u263E";
            button.title = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
        }
    }

    var saved = read();
    var current = (saved === "dark" || saved === "light") ? saved : DEFAULT;
    apply(current);                   // runs before the page paints, so there is no flash

    document.addEventListener("DOMContentLoaded", function () {
        var button = document.createElement("button");
        button.id = "theme-toggle";
        button.type = "button";
        button.className = "theme-toggle";

        var bar = document.querySelector(".top > span:last-child");
        if (bar) {
            bar.appendChild(button);                       // inside the top bar
        } else {
            button.className += " floating";               // login and register pages
            document.body.appendChild(button);
        }
        apply(current);

        button.addEventListener("click", function () {
            current = (current === "dark") ? "light" : "dark";
            write(current);
            apply(current);
        });
    });
})();