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

        // Re-apply active state to currently selected recipe
        const lastSelected = localStorage.getItem('lastSelectedRecipeOnList');
        if (lastSelected) {
            $('.recipe-item').removeClass('active');
            $(`.recipe-item[data-recipename="${lastSelected}"]`).addClass('active');
        }
    });

    // Render markdown when a recipe row is clicked
    const contentDiv = document.getElementById('markdownContent');

    function loadRecipe(recipename, $item) {
        $('.recipe-item').removeClass('active');
        $item.addClass('active');

        // Save to localStorage
        localStorage.setItem('lastSelectedRecipeOnList', recipename);

        fetch(`/markdown/recipe/${recipename}`)
            .then(res => res.json())
            .then(data => {
                contentDiv.innerHTML = data.content;
            })
            .catch(() => {
                contentDiv.innerHTML = '<p style="color:red;">Failed to load recipe.</p>';
            });
    }

    // Use event delegation since recipe items are in multiple groups
    $(document).on('click', '.recipe-item', function(e) {
        // Don't trigger when clicking the button
        if ($(e.target).closest('.add-recipe').length) {
            return;
        }

        const recipename = $(this).data('recipename');
        loadRecipe(recipename, $(this));
    });

    // Load last selected recipe on page load
    const lastSelected = localStorage.getItem('lastSelectedRecipeOnList');
    if (lastSelected) {
        const $item = $(`.recipe-item[data-recipename="${lastSelected}"]`);
        if ($item.length) {
            // Small delay to ensure DOM is ready
            setTimeout(function() {
                loadRecipe(lastSelected, $item);

                // Scroll to the recipe if it's not visible
                const itemTop = $item.offset().top;
                const itemHeight = $item.outerHeight();
                const windowTop = $(window).scrollTop();
                const windowHeight = $(window).height();

                // Check if item is outside viewport
                if (itemTop < windowTop || itemTop + itemHeight > windowTop + windowHeight) {
                    $('html, body').animate({
                        scrollTop: itemTop - (windowHeight / 2) + (itemHeight / 2)
                    }, 300);
                }
            }, 100);
        }
    }

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
