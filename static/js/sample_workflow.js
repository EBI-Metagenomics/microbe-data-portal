(function () {
    "use strict";

    const workflow = document.querySelector('[data-workflow-mode="list"]');
    const form = document.getElementById("sample_filters");
    const dialog = document.getElementById("workflow-filter-dialog");
    const showDialog = document.getElementById("show-workflow-filters");
    const closeDialog = document.getElementById("close-workflow-filters");
    const workflowFields = document.getElementById("workflow-form-fields");
    if (!workflow || !form) {
        return;
    }

    const status = document.getElementById("workflow-filter-status");
    const choices = Array.from(
        workflow.querySelectorAll("[data-workflow-filter-name]")
    );

    function setScope() {
        const environment = form.elements.namedItem("environment");
        const experimentType = form.elements.namedItem("experiment_type");
        if (environment) {
            environment.value = "Soil";
        }
        if (experimentType) {
            experimentType.value = "Cryopreservation";
        }
    }

    function refreshChoiceStates() {
        const selectedLabels = [];
        choices.forEach((choice) => {
            const field = form.elements.namedItem(choice.dataset.workflowFilterName);
            const selected = field && field.value === choice.dataset.workflowFilterValue;
            choice.classList.toggle("is-selected", Boolean(selected));
            choice.setAttribute("aria-current", selected ? "true" : "false");
            if (selected) {
                selectedLabels.push(choice.dataset.workflowLabel);
            }
        });
        status.textContent = selectedLabels.length
            ? `Selected workflow filters: ${selectedLabels.join(", ")}.`
            : "Select one choice in each column, then apply the sample filters.";
    }

    choices.forEach((choice) => {
        choice.addEventListener("click", (event) => {
            event.preventDefault();
            const field = form.elements.namedItem(choice.dataset.workflowFilterName);
            if (!field) {
                window.location.assign(choice.href);
                return;
            }
            setScope();
            field.value =
                field.value === choice.dataset.workflowFilterValue
                    ? ""
                    : choice.dataset.workflowFilterValue;
            field.dispatchEvent(new Event("change", { bubbles: true }));
            if (workflowFields) {
                workflowFields.open = true;
            }
            refreshChoiceStates();
        });
    });

    document
        .getElementById("clear-workflow-filters")
        .addEventListener("click", () => {
            Array.from(form.elements).forEach((field) => {
                if (field.name && field.name.startsWith("workflow_")) {
                    field.value = "";
                }
            });
            refreshChoiceStates();
        });

    if (dialog && showDialog && closeDialog) {
        showDialog.addEventListener("click", () => dialog.showModal());
        closeDialog.addEventListener("click", () => dialog.close());
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) {
                dialog.close();
            }
        });
    }

    refreshChoiceStates();
})();
