(function () {
    var body = document.body;
    var cartDrawer = document.getElementById("cart-drawer");
    var cartBackdrop = document.querySelector(".cart-drawer-backdrop");
    var cartTriggers = document.querySelectorAll("[data-cart-trigger]");
    var cartCloseButtons = document.querySelectorAll("[data-cart-close]");
    var darkModeToggle = document.getElementById("dark-mode-toggle");
    var THEME_STORAGE_KEY = "alomana-theme";
    var escapeCount = 0;
    var escapeTimer = null;

    function getSavedTheme() {
        try {
            return window.localStorage.getItem(THEME_STORAGE_KEY);
        } catch (error) {
            return null;
        }
    }

    function saveTheme(theme) {
        try {
            window.localStorage.setItem(THEME_STORAGE_KEY, theme);
        } catch (error) {
            return;
        }
    }

    function applyTheme(theme) {
        var isDarkTheme = theme === "dark";
        body.classList.toggle("dark-theme", isDarkTheme);
        if (darkModeToggle) {
            darkModeToggle.checked = isDarkTheme;
        }
    }

    function openCart(event) {
        if (event) {
            event.preventDefault();
        }
        if (!cartDrawer) {
            return;
        }
        cartDrawer.setAttribute("aria-hidden", "false");
        if (cartBackdrop) {
            cartBackdrop.hidden = false;
        }
        body.classList.add("cart-drawer-open");
    }

    function closeCart() {
        if (!cartDrawer) {
            return;
        }
        cartDrawer.setAttribute("aria-hidden", "true");
        if (cartBackdrop) {
            cartBackdrop.hidden = true;
        }
        body.classList.remove("cart-drawer-open");
    }

    function triggerQuickExit(event) {
        if (event) {
            event.preventDefault();
        }
        if (!darkModeToggle) {
            return;
        }
        body.classList.add("quick-exit-active");
        closeCart();
        sessionStorage.clear();
        setTimeout(function () {
            window.location.replace(darkModeToggle.getAttribute("data-exit-url"));
        }, 80);
    }

    cartTriggers.forEach(function (trigger) {
        trigger.addEventListener("click", openCart);
    });

    cartCloseButtons.forEach(function (button) {
        button.addEventListener("click", closeCart);
    });

    if (darkModeToggle) {
        var savedTheme = getSavedTheme();
        if (!savedTheme && window.matchMedia) {
            savedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        }
        applyTheme(savedTheme || "light");

        darkModeToggle.addEventListener("change", function () {
            var nextTheme = darkModeToggle.checked ? "dark" : "light";
            applyTheme(nextTheme);
            saveTheme(nextTheme);
        });
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            if (body.classList.contains("cart-drawer-open")) {
                closeCart();
                return;
            }

            escapeCount += 1;
            clearTimeout(escapeTimer);
            escapeTimer = setTimeout(function () {
                escapeCount = 0;
            }, 900);

            if (escapeCount >= 2) {
                escapeCount = 0;
                triggerQuickExit();
            }
        }
    });

    if (document.querySelector(".flash-success") && cartDrawer) {
        var successMessages = Array.prototype.slice.call(document.querySelectorAll(".flash-success"));
        var shouldOpenCart = successMessages.some(function (node) {
            return /adicionado ao carrinho/i.test(node.textContent || "");
        });
        if (shouldOpenCart) {
            openCart();
        }
    }
})();
