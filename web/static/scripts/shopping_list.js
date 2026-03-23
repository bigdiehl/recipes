$(document).ready(function () {

    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Remove recipe and refresh shopping list
    $('.remove-recipe').click(function () {
        const button = $(this);
        const recipeSlug = button.data('id');

        $.post(`/deselect/${recipeSlug}`, function (data) {
            if (data.success) {
                // Dispose tooltip before removing element
                const tooltip = bootstrap.Tooltip.getInstance(button[0]);
                if (tooltip) tooltip.dispose();

                button.closest('.recipe-item').remove();

                fetch("/markdown/shopping_list")
                    .then(res => res.json())
                    .then(data => {
                        document.getElementById("markdownContent").innerHTML = data.html;
                    });
            } else {
                alert('Remove failed.');
            }
        });
    });

    // Email shopping list
    $("#emailListBtn").on("click", function () {
        const email = $("#emailAddress").val();

        $.ajax({
            url: "/send_list",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ email: email }),
            success: function (response) {
                if (response.success) {
                    alert("Shopping list sent to " + email);
                } else {
                    alert("Failed to send email.");
                }
            },
            error: function () {
                alert("Error sending request to server.");
            }
        });
    });

});
