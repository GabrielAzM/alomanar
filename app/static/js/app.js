(function () {
    var body = document.body;
    var cartDrawer = document.getElementById("cart-drawer");
    var cartBackdrop = document.querySelector(".cart-drawer-backdrop");
    var cartTriggers = document.querySelectorAll("[data-cart-trigger]");
    var cartCloseButtons = document.querySelectorAll("[data-cart-close]");
    var darkModeToggle = document.getElementById("dark-mode-toggle");
    var escapeCount = 0;
    var escapeTimer = null;

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
        darkModeToggle.checked = false;
        darkModeToggle.addEventListener("change", function () {
            if (darkModeToggle.checked) {
                triggerQuickExit();
            }
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
