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
  const totalSteps = steps.length;

  if (!totalSteps || !prevButton || !nextButton) {
    return;
  }

  let currentStepIndex = steps.findIndex((step) => !step.hasAttribute('hidden'));
  if (currentStepIndex < 0) {
    currentStepIndex = 0;
  }

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

  form.addEventListener('submit', () => {
    if (finalActions && finalActions.hidden) {
      finalActions.hidden = false;
    }
  });

  updateStepsVisibility(false, false);
})();
