

// document.addEventListener('DOMContentLoaded', function() {
//     document.querySelectorAll('.remove-recipe').forEach(function(btn) {
//         btn.addEventListener('click', function() {
//             this.closest('.recipe-item').remove();
//         });
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
                button.closest('.recipe-item').remove();
            } else {
                alert('Toggle failed.');
            }
        });
    });
});