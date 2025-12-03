(function () {
  const form = document.getElementById('consultant-form');
  if (!form) {
    return;
  }

  const steps = Array.from(form.querySelectorAll('.wizard-step'));
  const progressItems = Array.from(form.querySelectorAll('.wizard-progress-item'));
  const stepCounter = form.querySelector('#wizard-step-counter');
  const prevButton = form.querySelector('.wizard-prev');
  const nextButton = form.querySelector('.wizard-next');
  const finalActions = form.querySelector('[data-final-actions]');
  const summaryElement = form.querySelector('[data-validation-summary]');
  const summaryList = form.querySelector('[data-validation-summary-list]');
  const summaryText = form.querySelector('[data-validation-summary-text]');
  const totalSteps = steps.length;

  if (!totalSteps || !prevButton || !nextButton) {
    return;
  }

  let currentStepIndex = steps.findIndex((step) => !step.hasAttribute('hidden'));
  if (currentStepIndex < 0) {
    currentStepIndex = 0;
  }

  const clearValidationSummary = () => {
    if (summaryElement) {
      summaryElement.hidden = true;
    }
    if (summaryList) {
      summaryList.innerHTML = '';
    }
  };

  const focusStep = (step) => {
    if (!step) {
      return;
    }

    window.requestAnimationFrame(() => {
      const focusTarget =
        step.querySelector('[data-step-focus]') ||
        step.querySelector('input, select, textarea, button, [tabindex]:not([tabindex="-1"])');

      if (focusTarget) {
        const previousTabIndex = focusTarget.getAttribute('tabindex');
        if (previousTabIndex === null) {
          focusTarget.setAttribute('tabindex', '-1');
        }
        focusTarget.focus({ preventScroll: false });
        if (previousTabIndex === null) {
          focusTarget.removeAttribute('tabindex');
        }
      }
    });
  };

  const updateStepCounter = () => {
    if (!stepCounter) {
      return;
    }

    stepCounter.textContent = `Step ${currentStepIndex + 1} of ${totalSteps}`;
  };

  const updateProgress = () => {
    progressItems.forEach((item, index) => {
      if (index === currentStepIndex) {
        item.setAttribute('aria-current', 'step');
        item.classList.add('is-active');
      } else {
        item.removeAttribute('aria-current');
        item.classList.remove('is-active');
      }
    });
  };

  const updateNavigation = () => {
    const isFirstStep = currentStepIndex === 0;
    const isLastStep = currentStepIndex === totalSteps - 1;

    prevButton.disabled = isFirstStep;
    prevButton.setAttribute('aria-disabled', isFirstStep ? 'true' : 'false');

    if (isLastStep) {
      nextButton.hidden = true;
      nextButton.setAttribute('aria-hidden', 'true');
    } else {
      nextButton.hidden = false;
      nextButton.removeAttribute('aria-hidden');
      if (currentStepIndex === totalSteps - 2) {
        nextButton.textContent = 'Review & submit';
      } else {
        nextButton.textContent = 'Next step';
      }
    }

    if (finalActions) {
      if (isLastStep) {
        finalActions.hidden = false;
      } else {
        finalActions.hidden = true;
      }
    }
  };

  const triggerAutoSave = () => {
    const autoSaveEvent = new CustomEvent('consultant:auto-save', { bubbles: true });
    form.dispatchEvent(autoSaveEvent);
  };

  const updateStepsVisibility = (triggerSave = false, shouldFocus = true) => {
    steps.forEach((step, index) => {
      if (index === currentStepIndex) {
        step.removeAttribute('hidden');
        step.classList.add('is-active');
      } else {
        step.setAttribute('hidden', 'hidden');
        step.classList.remove('is-active');
      }
    });

    updateProgress();
    updateStepCounter();
    updateNavigation();
    if (shouldFocus) {
      focusStep(steps[currentStepIndex]);
    }

    if (triggerSave) {
      triggerAutoSave();
    }
  };

  const validateCurrentStep = () => {
    const currentStep = steps[currentStepIndex];
    if (!currentStep) {
      return true;
    }

    const fields = Array.from(
      currentStep.querySelectorAll('input, select, textarea'),
    ).filter((field) => !field.disabled && field.offsetParent !== null);

    for (const field of fields) {
      if (!field.checkValidity()) {
        field.reportValidity();
        field.focus();
        return false;
      }
    }

    return true;
  };

  const goToStep = (newIndex) => {
    if (newIndex < 0 || newIndex >= totalSteps || newIndex === currentStepIndex) {
      return;
    }

    currentStepIndex = newIndex;
    updateStepsVisibility(true, true);
  };

  prevButton.addEventListener('click', () => {
    if (currentStepIndex === 0) {
      return;
    }
    goToStep(currentStepIndex - 1);
  });

  nextButton.addEventListener('click', () => {
    if (!validateCurrentStep()) {
      return;
    }

    goToStep(currentStepIndex + 1);
  });

  form.addEventListener('input', (event) => {
    if (!(event.target instanceof HTMLElement)) {
      return;
    }

    const field = event.target.closest('input, select, textarea');
    if (!field) {
      return;
    }

    field.removeAttribute('aria-invalid');
    const container = field.closest('.form-field');
    if (container) {
      container.classList.remove('has-error');
    }
  });

  const collectServerErrors = () => {
    const errors = [];

    steps.forEach((step, stepIndex) => {
      const errorItems = Array.from(step.querySelectorAll('.errorlist li'));

      errorItems.forEach((item) => {
        const fieldContainer = item.closest('.form-field');
        const field = fieldContainer
          ? fieldContainer.querySelector('input, select, textarea')
          : null;
        const label = fieldContainer ? fieldContainer.querySelector('label') : null;

        if (field) {
          field.setAttribute('aria-invalid', 'true');
        }
        if (fieldContainer) {
          fieldContainer.classList.add('has-error');
        }

        errors.push({
          label: label ? label.textContent.trim() : field?.name || 'This field',
          message: item.textContent.trim(),
          stepIndex,
          field,
        });
      });
    });

    return errors;
  };

  const describeField = (field) => {
    if (!field) {
      return 'This field';
    }

    if (field.labels && field.labels.length) {
      return field.labels[0].textContent.trim();
    }

    const label = form.querySelector(`label[for="${field.id}"]`);
    if (label) {
      return label.textContent.trim();
    }

    return field.name || 'This field';
  };

  const renderValidationSummary = (items, introText) => {
    if (!summaryElement || !summaryList) {
      return;
    }

    if (introText && summaryText) {
      summaryText.textContent = introText;
    }

    summaryList.innerHTML = '';
    items.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = `${item.label}: ${item.message}`;
      summaryList.appendChild(li);
    });

    summaryElement.hidden = items.length === 0;
    if (!summaryElement.hidden) {
      summaryElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const collectInvalidFields = () => {
    const fields = Array.from(form.querySelectorAll('input, select, textarea')).filter(
      (field) => !field.disabled,
    );

    const invalid = [];

    fields.forEach((field) => {
      field.removeAttribute('aria-invalid');
      const container = field.closest('.form-field');
      if (container) {
        container.classList.remove('has-error');
      }

      if (!field.checkValidity()) {
        const stepIndex = steps.findIndex((step) => step.contains(field));
        invalid.push({
          field,
          stepIndex,
          label: describeField(field),
          message: field.validationMessage || 'Please fill out this field.',
        });
        field.setAttribute('aria-invalid', 'true');
        if (container) {
          container.classList.add('has-error');
        }
      }
    });

    return invalid;
  };

  form.addEventListener('submit', (event) => {
    if (finalActions && finalActions.hidden) {
      finalActions.hidden = false;
    }

    const submitter = event.submitter;
    const isFinalSubmission = submitter && submitter.value === 'submit';

    if (!isFinalSubmission) {
      clearValidationSummary();
      return;
    }

    const invalidFields = collectInvalidFields();

    if (invalidFields.length) {
      event.preventDefault();
      const firstInvalid = invalidFields[0];

      if (typeof firstInvalid.stepIndex === 'number' && firstInvalid.stepIndex !== currentStepIndex) {
        currentStepIndex = firstInvalid.stepIndex;
        updateStepsVisibility(false, true);
      }

      renderValidationSummary(
        invalidFields.map((item) => ({
          label: item.label,
          message: item.message,
        })),
        'Complete the highlighted fields before submitting your application.',
      );

      if (firstInvalid.field) {
        firstInvalid.field.reportValidity();
        firstInvalid.field.focus();
      }
    } else {
      clearValidationSummary();
    }
  });

  const serverErrors = collectServerErrors();
  const firstErrorStepIndex = serverErrors.find((item) => typeof item.stepIndex === 'number');
  if (firstErrorStepIndex && typeof firstErrorStepIndex.stepIndex === 'number') {
    currentStepIndex = firstErrorStepIndex.stepIndex;
  }

  updateStepsVisibility(false, false);

  if (serverErrors.length) {
    renderValidationSummary(serverErrors, 'Complete the highlighted fields to submit your application.');
  }
})();
