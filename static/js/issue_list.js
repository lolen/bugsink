"use strict";

function toggleContainedCheckbox(circleDiv) {
    const checkbox = circleDiv.querySelector("[type=\"checkbox\"]");
    checkbox.checked = !checkbox.checked;
}

function matchIssueCheckboxesStateToMain(elementContainingMainCheckbox) {
    const mainCheckbox = elementContainingMainCheckbox.querySelector("[type=\"checkbox\"]");
    const checkboxes = document.querySelectorAll(".js-issue-checkbox");
    for (let i = 0; i < checkboxes.length; i++) {
        checkboxes[i].checked = mainCheckbox.checked;
    }
}

function matchMainCheckboxStateToIssueCheckboxes() {
    const checkboxes = document.querySelectorAll(".js-issue-checkbox");
    let allChecked = true;
    let allUnchecked = true;

    for (let i = 0; i < checkboxes.length; i++) {
        if (checkboxes[i].checked) {
            allUnchecked = false;
        }
        if (!checkboxes[i].checked) {
            allChecked = false;
        }
        if (!allChecked && !allUnchecked) {
            break;
        }
    }

    const mainCheckbox = document.querySelector(".js-main-checkbox");
    if (allChecked) {
        mainCheckbox.checked = true;
    }
    if (allUnchecked) {
        mainCheckbox.checked = false;
    }
}

function followContainedLink(circleDiv) {
    const link = circleDiv.querySelector("a");
    window.location.href = link.href;
}

document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("issue-search-input");
    if (!input) {
        return;
    }
    const suggestBox = document.getElementById("issue-search-suggestions");
    const suggestUrl = input.dataset.suggestUrl;

    function getCurrentToken() {
        // the whitespace-delimited word the cursor is currently in/next to, since a query can have multiple
        // key:value tokens (e.g. "environment:production release:1.2") and we only want to suggest for the one
        // being edited.
        const value = input.value;
        const pos = input.selectionStart;
        let start = pos;
        while (start > 0 && !/\s/.test(value[start - 1])) start--;
        let end = pos;
        while (end < value.length && !/\s/.test(value[end])) end++;
        return {text: value.slice(start, end), start: start, end: end};
    }

    function replaceToken(token, replacement) {
        input.value = input.value.slice(0, token.start) + replacement + input.value.slice(token.end);
        const newPos = token.start + replacement.length;
        input.setSelectionRange(newPos, newPos);
    }

    function hideSuggestions() {
        suggestBox.classList.add("hidden");
        suggestBox.innerHTML = "";
    }

    function renderSuggestions(items, onPick) {
        if (!items.length) {
            hideSuggestions();
            return;
        }
        suggestBox.innerHTML = "";
        items.forEach((item) => {
            const el = document.createElement("div");
            el.className = "px-3 py-2 cursor-pointer hover:bg-raised text-ink";
            el.textContent = item;
            // mousedown (not click) fires before the input's blur, so we can act on the pick before the
            // outside-click / blur handling below hides the dropdown out from under us.
            el.addEventListener("mousedown", (event) => {
                event.preventDefault();
                onPick(item);
            });
            suggestBox.appendChild(el);
        });
        suggestBox.classList.remove("hidden");
    }

    let debounceTimer = null;
    let abortController = null;

    function fetchSuggestions() {
        const token = getCurrentToken();
        const colonIndex = token.text.indexOf(":");

        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();

        let url;
        let mode;
        if (colonIndex === -1) {
            url = suggestUrl + "?prefix=" + encodeURIComponent(token.text);
            mode = "key";
        } else {
            const key = token.text.slice(0, colonIndex);
            const valuePrefix = token.text.slice(colonIndex + 1);
            url = suggestUrl + "?key=" + encodeURIComponent(key) + "&prefix=" + encodeURIComponent(valuePrefix);
            mode = "value";
        }

        fetch(url, {signal: abortController.signal})
            .then((response) => (response.ok ? response.json() : null))
            .then((data) => {
                if (!data) {
                    return;
                }
                if (mode === "key") {
                    renderSuggestions(data.keys || [], (picked) => {
                        replaceToken(token, picked + ":");
                        input.focus();
                        fetchSuggestions();
                    });
                } else {
                    const key = token.text.slice(0, token.text.indexOf(":"));
                    renderSuggestions(data.values || [], (picked) => {
                        replaceToken(token, key + ":" + picked + " ");
                        input.focus();
                        hideSuggestions();
                    });
                }
            })
            .catch(() => {
                // AbortError from a superseded request, or a network hiccup; either way there's nothing
                // actionable to do here, the next keystroke will just try again.
            });
    }

    function scheduleFetch() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fetchSuggestions, 150);
    }

    input.addEventListener("input", scheduleFetch);
    input.addEventListener("focus", scheduleFetch);
    input.addEventListener("keyup", (event) => {
        // moving the cursor can change which token is "current" without firing an "input" event.
        if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            scheduleFetch();
        }
    });
    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            hideSuggestions();
        }
    });

    document.addEventListener("click", (event) => {
        if (event.target !== input && !suggestBox.contains(event.target)) {
            hideSuggestions();
        }
    });
});
