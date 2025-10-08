(function () {
  const form = document.getElementById('consultant-form');
  if (!form) {
    return;
  }

  const autosaveUrl = form.dataset.autosaveUrl;
  const lastSavedAt = form.dataset.lastSaved || '';
  const statusElement = document.getElementById('draft-status');
  const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
  const csrfToken = csrfInput ? csrfInput.value : '';

  if (!autosaveUrl) {
    return;
  }

  let inactivityTimer = null;
  let isSaving = false;
  let lastPayloadSignature = null;

  const formatTimestamp = (isoString) => {
    try {
      const date = new Date(isoString);
      if (Number.isNaN(date.getTime())) {
        return null;
      }
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (error) {
      return null;
    }
  };

  const updateStatus = (isoString) => {
    if (!statusElement) {
      return;
    }

    const formattedTime = formatTimestamp(isoString);
    if (formattedTime) {
      statusElement.textContent = `Draft saved at ${formattedTime}`;
    } else {
      statusElement.textContent = 'Draft saved.';
    }
  };

  if (lastSavedAt) {
    updateStatus(lastSavedAt);
  }

  const buildPayload = () => {
    const payload = {};
    const ignoredTypes = new Set(['file']);

    Array.from(form.elements).forEach((element) => {
      if (!(element instanceof HTMLElement)) {
        return;
      }

      const { name, type } = element;
      if (!name || ignoredTypes.has(type)) {
        return;
      }

      if (type === 'checkbox') {
        payload[name] = element.checked;
      } else if (type === 'radio') {
        if (element.checked) {
          payload[name] = element.value;
        } else if (!(name in payload)) {
          payload[name] = '';
        }
      } else {
        payload[name] = element.value;
      }
    });

    payload.action = 'draft';
    return payload;
  };

  const scheduleInactivitySave = () => {
    if (inactivityTimer) {
      window.clearTimeout(inactivityTimer);
    }

    inactivityTimer = window.setTimeout(() => {
      void autoSave();
    }, 15000);
  };

  const handleResponse = (result, signature) => {
    if (!result) {
      return;
    }

    if (result.status === 'saved') {
      if (result.timestamp) {
        updateStatus(result.timestamp);
      }
      lastPayloadSignature = signature;
    } else if (result.status === 'unchanged') {
      lastPayloadSignature = signature;
    } else if (result.status === 'skipped') {
      lastPayloadSignature = null;
      if (statusElement && result.message) {
        statusElement.textContent = result.message;
      }
    } else {
      lastPayloadSignature = null;
    }
  };

  const autoSave = async () => {
    if (isSaving) {
      return;
    }

    const payload = buildPayload();
    const signature = JSON.stringify(payload);

    if (signature === lastPayloadSignature) {
      return;
    }

    isSaving = true;

    try {
      const response = await fetch(autosaveUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        lastPayloadSignature = null;
        return;
      }

      const result = await response.json();
      handleResponse(result, signature);
    } catch (error) {
      lastPayloadSignature = null;
    } finally {
      isSaving = false;
    }
  };

  form.addEventListener(
    'blur',
    (event) => {
      if (!(event.target instanceof HTMLElement)) {
        return;
      }
      if (!event.target.name) {
        return;
      }
      void autoSave();
    },
    true,
  );

  form.addEventListener('input', () => {
    scheduleInactivitySave();
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      void autoSave();
    }
  });

  window.addEventListener('beforeunload', () => {
    if (isSaving) {
      return;
    }
    void autoSave();
  });
})();
