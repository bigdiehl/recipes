


const recipeItems = document.querySelectorAll('.recipe-item');
const contentDiv = document.getElementById('markdownContent');

// Render Markdown for selected recipe
recipeItems.forEach(item => {
    item.addEventListener('click', () => {
        const recipename = item.dataset.recipename;

        // Highlight selected
        document.querySelectorAll('.recipe-item').forEach(el => el.classList.remove('active'));
        item.classList.add('active');

        // Fetch rendered markdown
        fetch(`/markdown/api/${recipename}`)
            .then(res => res.json())
            .then(data => {
                contentDiv.innerHTML = data.content;
            })
            .catch(err => {
                contentDiv.innerHTML = '<p style="color:red;">Failed to load recipe.</p>';
            });
    });
});

// Initialize Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Toggle logic with AJAX
$(document).ready(function () {
    $('.add-recipe').click(function () {
        const button = $(this);
        const recipeId = button.data('id');

        $.post(`/recipes_list/toggle/${recipeId}`, function (data) {
            if (data.success) {
                const selected = data.selected;
                button.text(selected ? '✔' : '+');
                // Update button class
                if (selected) {
                    button.removeClass('btn-success').addClass('btn-primary');
                } else {
                    button.removeClass('btn-primary').addClass('btn-success');
                }
                button.data('selected', selected);
            } else {
                alert('Toggle failed.');
            }
        });
    });
});
