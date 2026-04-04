$(document).ready(function () {

    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle grouping toggle
    $('input[name="groupBy"]').change(function () {
        const groupBy = $(this).val();
        if (groupBy === 'category') {
            $('#categoryGroups').show();
            $('#mealGroups').hide();
        } else if (groupBy === 'meal') {
            $('#categoryGroups').hide();
            $('#mealGroups').show();
        }
    });

    // Render markdown when a recipe row is clicked
    const contentDiv = document.getElementById('markdownContent');

    // Use event delegation since recipe items are in multiple groups
    $(document).on('click', '.recipe-item', function(e) {
        // Don't trigger when clicking the button
        if ($(e.target).closest('.add-recipe').length) {
            return;
        }

        const recipename = $(this).data('recipename');

        $('.recipe-item').removeClass('active');
        $(this).addClass('active');

        fetch(`/markdown/recipe/${recipename}`)
            .then(res => res.json())
            .then(data => {
                contentDiv.innerHTML = data.content;
            })
            .catch(() => {
                contentDiv.innerHTML = '<p style="color:red;">Failed to load recipe.</p>';
            });
    });

    // Toggle selected state (use event delegation)
    $(document).on('click', '.add-recipe', function (e) {
        e.stopPropagation(); // Prevent triggering recipe-item click
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
