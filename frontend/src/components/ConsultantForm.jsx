import { useState } from 'react';

export async function checkConsultantUniqueness({
  email,
  id_number,
  registration_number,
  nationality,
  consultantId,
}) {
  const payload = {
    email: email || undefined,
    id_number: id_number || undefined,
    registration_number: registration_number || undefined,
    nationality: nationality || undefined,
    consultant_id: consultantId || undefined,
  };

  const response = await fetch('/api/consultants/validate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 204) {
    return {};
  }

  let data = {};
  try {
    data = await response.json();
  } catch (error) {
    data = {};
  }

  if (!response.ok) {
    const errors = data?.errors || {};
    return Object.keys(errors).reduce((accumulator, key) => {
      const value = errors[key];
      accumulator[key] = Array.isArray(value) ? value[0] : value;
      return accumulator;
    }, {});
  }

  return {};
}

export default function ConsultantForm({ onSubmit, consultantId }) {
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    id_number: '',
    nationality: '',
    registration_number: '',
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((previous) => ({
      ...previous,
      [name]: value,
    }));
    setErrors((previous) => ({
      ...previous,
      [name]: undefined,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);

    const uniquenessErrors = await checkConsultantUniqueness({
      email: formData.email,
      id_number: formData.id_number,
      registration_number: formData.registration_number,
      nationality: formData.nationality,
      consultantId,
    });

    if (Object.keys(uniquenessErrors).length > 0) {
      setErrors(uniquenessErrors);
      setIsSubmitting(false);
      return;
    }

    setErrors({});

    if (onSubmit) {
      await onSubmit(formData);
    }

    setIsSubmitting(false);
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div>
        <label htmlFor="full_name">Full name</label>
        <input
          id="full_name"
          name="full_name"
          type="text"
          value={formData.full_name}
          onChange={handleChange}
        />
      </div>

      <div>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          required
        />
        {errors.email && <p role="alert">{errors.email}</p>}
      </div>

      <div>
        <label htmlFor="id_number">ID Number</label>
        <input
          id="id_number"
          name="id_number"
          type="text"
          value={formData.id_number}
          onChange={handleChange}
          required
        />
        {errors.id_number && <p role="alert">{errors.id_number}</p>}
      </div>

      <div>
        <label htmlFor="nationality">Nationality</label>
        <input
          id="nationality"
          name="nationality"
          type="text"
          value={formData.nationality}
          onChange={handleChange}
        />
      </div>

      <div>
        <label htmlFor="registration_number">Registration number</label>
        <input
          id="registration_number"
          name="registration_number"
          type="text"
          value={formData.registration_number}
          onChange={handleChange}
        />
        {errors.registration_number && (
          <p role="alert">{errors.registration_number}</p>
        )}
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Submitting…' : 'Submit'}
      </button>
    </form>
  );
}
