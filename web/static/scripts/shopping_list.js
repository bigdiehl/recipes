

// document.addEventListener('DOMContentLoaded', function() {
//     document.querySelectorAll('.remove-recipe').forEach(function(btn) {
//         btn.addEventListener('click', function() {
//             this.closest('.recipe-item').remove();
//         });
//     });
// });

// Render Markdown shopping list for selected recipe
// document.querySelectorAll(".recipe-item").forEach(btn => {
//     btn.addEventListener("click", () => {
//     fetch("/markdown/shopping_list")
//     .then(res => res.json())
//     .then(data => {
//         document.getElementById("markdownContent").innerHTML = data.html;
//     });
//     });
// });

// Initialize Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Remove logic with AJAX
$(document).ready(function () {
    $('.remove-recipe').click(function () {
        const button = $(this);
        const recipeId = button.data('id');

        $.post(`/deselect/${recipeId}`, function (data) {
            if (data.success) {

                 // Dispose tooltip before removing element
                const tooltip = bootstrap.Tooltip.getInstance(button[0]);
                if (tooltip) {
                    tooltip.dispose();
                }

                button.closest('.recipe-item').remove();

                fetch("/markdown/shopping_list")
                    .then(res => res.json())
                    .then(data => {
                        document.getElementById("markdownContent").innerHTML = data.html;
                });

            } else {
                alert('Toggle failed.');
            }
        });

    });
});

$(document).ready(function () {
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