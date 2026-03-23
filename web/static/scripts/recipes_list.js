$(document).ready(function () {

    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Render markdown when a recipe row is clicked
    const contentDiv = document.getElementById('markdownContent');
    document.querySelectorAll('.recipe-item').forEach(item => {
        item.addEventListener('click', () => {
            const recipename = item.dataset.recipename;

            document.querySelectorAll('.recipe-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');

            fetch(`/markdown/recipe/${recipename}`)
                .then(res => res.json())
                .then(data => {
                    contentDiv.innerHTML = data.content;
                })
                .catch(() => {
                    contentDiv.innerHTML = '<p style="color:red;">Failed to load recipe.</p>';
                });
        });
    });

    // Toggle selected state
    $('.add-recipe').click(function () {
        const button = $(this);
        const recipeSlug = button.data('id');

        $.post(`/recipes_list/toggle/${recipeSlug}`, function (data) {
            if (data.success) {
                const selected = data.selected;
                button.text(selected ? '✔' : '+');
                button.toggleClass('btn-primary', selected);
                button.toggleClass('btn-success', !selected);
                button.data('selected', selected);
            } else {
                alert('Toggle failed.');
            }
        });
    });

});
