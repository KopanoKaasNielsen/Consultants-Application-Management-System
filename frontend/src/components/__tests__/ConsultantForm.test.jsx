import { checkConsultantUniqueness } from '../ConsultantForm.jsx';

describe('checkConsultantUniqueness', () => {
  afterEach(() => {
    if (global.fetch) {
      global.fetch.mockClear();
    }
  });

  it('returns backend validation errors when duplicates are reported', async () => {
    const errors = {
      email: 'A consultant with this email already exists.',
      id_number: 'A consultant with this ID number already exists.',
    };

    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: jest.fn().mockResolvedValue({ errors }),
    });

    const result = await checkConsultantUniqueness({
      email: 'duplicate@example.com',
      id_number: '12345678',
      nationality: 'Kenya',
    });

    expect(fetch).toHaveBeenCalledWith(
      '/api/consultants/validate',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    expect(result).toEqual(errors);
  });

  it('returns empty object when backend accepts the values', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ valid: true }),
    });

    const result = await checkConsultantUniqueness({
      email: 'unique@example.com',
      id_number: '987654321',
      nationality: 'Kenya',
    });

    expect(result).toEqual({});
  });
});
