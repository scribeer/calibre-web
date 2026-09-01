/* AU-Books accessibility and theme behavior layered on the existing Bootstrap UI. */
(function() {
    "use strict";

    /* ======================================================================
       Theme switching
       ====================================================================== */

    var STORAGE_KEY = "aubooks-theme";
    var htmlEl = document.documentElement;
    var mediaQuery = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
    var currentPreference = null; // "system" | "light" | "dark"
    var systemListenerBound = false;

    function safeGetStorage(key) {
        try { return localStorage.getItem(key); } catch (e) { return null; }
    }

    function safeSetStorage(key, value) {
        try { localStorage.setItem(key, value); } catch (e) { /* noop */ }
    }

    function resolveTheme(preference) {
        if (preference === "light" || preference === "dark") {
            return preference;
        }
        return (mediaQuery && mediaQuery.matches) ? "dark" : "light";
    }

    function applyTheme(resolved) {
        htmlEl.setAttribute("data-theme", resolved);
    }

    function syncSelect(preference) {
        var sel = document.getElementById("aubooks-color-theme");
        if (sel) {
            sel.value = preference;
        }
    }

    function bindSystemListener() {
        if (systemListenerBound || !mediaQuery) return;
        systemListenerBound = true;
        mediaQuery.addEventListener("change", function() {
            if (currentPreference === "system") {
                applyTheme(resolveTheme("system"));
            }
        });
    }

    function setTheme(preference) {
        if (preference !== "light" && preference !== "dark") {
            preference = "system";
        }
        currentPreference = preference;
        safeSetStorage(STORAGE_KEY, preference);
        applyTheme(resolveTheme(preference));
        syncSelect(preference);
        if (preference === "system") {
            bindSystemListener();
        }
    }

    // Initialize from storage
    (function initTheme() {
        var stored = safeGetStorage(STORAGE_KEY);
        if (stored === "light" || stored === "dark") {
            currentPreference = stored;
        } else {
            currentPreference = "system";
        }
        applyTheme(resolveTheme(currentPreference));
        syncSelect(currentPreference);
        if (currentPreference === "system") {
            bindSystemListener();
        }
    })();

    // Bind select element
    $(document).on("change", "#aubooks-color-theme", function() {
        setTheme($(this).val());
    });

    // Cross-tab sync via storage event
    if (window.addEventListener) {
        window.addEventListener("storage", function(e) {
            if (e.key === STORAGE_KEY && e.newValue) {
                setTheme(e.newValue);
            }
        });
    }

    /* ======================================================================
       Accessibility: alerts, modals, focus
       ====================================================================== */

    function messageText(message) {
        return $("<div>").html(message || "").text().trim();
    }

    window.aubooksAnnounce = function(type, message) {
        var text = messageText(message);
        var isError = type === "danger" || type === "error";
        var $region = $(isError ? "#aubooks-live-alert" : "#aubooks-live-status");
        if (!text || !$region.length) {
            return;
        }
        $region.text("");
        window.setTimeout(function() {
            $region.text(text);
        }, 20);
    };

    function registerAlert(element) {
        var $alert = $(element);
        if ($alert.closest("#aubooks-live-status, #aubooks-live-alert").length) {
            return;
        }
        var isError = $alert.hasClass("alert-danger");
        $alert.attr("role", isError ? "alert" : "status");
        window.aubooksAnnounce(isError ? "danger" : "status", $alert.text());
    }

    if (window.MutationObserver) {
        new window.MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                $(mutation.addedNodes).each(function() {
                    if (this.nodeType !== 1) {
                        return;
                    }
                    if ($(this).hasClass("alert")) {
                        registerAlert(this);
                    }
                    $(this).find(".alert").each(function() {
                        registerAlert(this);
                    });
                });
                var $bookModal = $(mutation.target).closest("#bookDetailsModal:visible");
                if ($bookModal.length && !$bookModal.data("aubooks-content-focused")) {
                    var $heading = $bookModal.find(".modal-body #title").first();
                    if ($heading.length) {
                        $bookModal.data("aubooks-content-focused", true);
                        $heading.attr("tabindex", "-1").trigger("focus");
                    }
                }
            });
        }).observe(document.body, {childList: true, subtree: true});
    }

    function modalTabStops($modal) {
        return $modal.find("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])")
            .filter(":visible");
    }

    function labelModal($modal) {
        var $title = $modal.find(".modal-title:not(.hidden)").first();
        if (!$title.length) {
            return;
        }
        if (!$title.attr("id")) {
            $title.attr("id", ($modal.attr("id") || "aubooks-modal") + "-title");
        }
        $modal.attr("aria-labelledby", $title.attr("id")).removeAttr("aria-label");
    }

    $(document)
        .on("show.bs.modal", ".modal", function(event) {
            var $modal = $(this);
            this.aubooksTrigger = event.relatedTarget || document.activeElement;
            $modal.removeData("aubooks-content-focused");
            $modal.attr({tabindex: "-1", "aria-modal": "true"});
            if (!$modal.attr("role")) {
                $modal.attr("role", "dialog");
            }
            $modal.find(".modal-dialog").first().attr("role", "document");
            labelModal($modal);
        })
        .on("shown.bs.modal", ".modal", function() {
            var $modal = $(this);
            labelModal($modal);
            var $target = $modal.find("[data-modal-initial-focus]:visible").first();
            if (!$target.length) {
                $target = modalTabStops($modal).first();
            }
            ($target.length ? $target : $modal).trigger("focus");
        })
        .on("keydown", ".modal", function(event) {
            if (event.key !== "Tab") {
                return;
            }
            var $stops = modalTabStops($(this));
            if (!$stops.length) {
                event.preventDefault();
                $(this).trigger("focus");
                return;
            }
            var first = $stops.get(0);
            var last = $stops.get($stops.length - 1);
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        })
        .on("hidden.bs.modal", ".modal", function() {
            var trigger = this.aubooksTrigger;
            if (trigger && document.documentElement.contains(trigger) && $(trigger).is(":visible")) {
                trigger.focus();
            }
            this.aubooksTrigger = null;
        });

    $(document).on("click", ".aubooks-filter-controls button", function() {
        window.setTimeout(function() {
            $(".aubooks-filter-controls #asc, .aubooks-filter-controls #desc, .aubooks-filter-controls #sort_name, .aubooks-filter-controls #all, .aubooks-filter-controls .char")
                .each(function() {
                    $(this).attr("aria-pressed", $(this).hasClass("active") ? "true" : "false");
                });
        }, 0);
    });

    function loadDeferredCovers() {
        $("img[data-src]").each(function() {
            var $img = $(this);
            var src = $img.attr("data-src");
            if (src) {
                $img.removeAttr("data-src").attr("src", src);
            }
        });
    }

    if (window.requestIdleCallback) {
        window.requestIdleCallback(loadDeferredCovers, {timeout: 3000});
    } else {
        window.addEventListener("load", loadDeferredCovers);
    }
})();
