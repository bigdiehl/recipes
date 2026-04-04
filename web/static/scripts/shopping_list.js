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
        const button = $(this);
        const email = $("#emailAddress").val().trim();

        if (!email) {
            alert("Please enter at least one email address.");
            return;
        }

        // Disable button and show loading state
        button.prop("disabled", true);
        const originalText = button.text();
        button.text("Sending...");

        $.ajax({
            url: "/send_list",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ email: email }),
            success: function (response) {
                if (response.success) {
                    alert(response.message || "Shopping list sent successfully!");
                } else {
                    alert("Failed to send email: " + (response.error || "Unknown error"));
                }
            },
            error: function (xhr) {
                let errorMsg = "Error sending email.";
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                alert(errorMsg);
            },
            complete: function () {
                // Re-enable button
                button.prop("disabled", false);
                button.text(originalText);
            }
        });
    });

});
