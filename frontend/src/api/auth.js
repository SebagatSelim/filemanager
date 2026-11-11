import api from './client';

/** POST /api/auth/register -> { user_id, message } */
export async function register({ name, email, password }) {
  const { data } = await api.post(
    '/auth/register',
    { name, email, password },
    { skipAuth: true, skipAuthRedirect: true },
  );
  return data;
}

/** POST /api/auth/login -> { access_token, expires_in, user } */
export async function login({ email, password }) {
  const { data } = await api.post(
    '/auth/login',
    { email, password },
    { skipAuth: true, skipAuthRedirect: true },
  );
  return data;
}

/** GET /api/auth/me -> { user_id, name, email, created_at } */
export async function getMe() {
  const { data } = await api.get('/auth/me');
  return data;
}

/** POST /api/auth/logout -> 204. Never triggers the 401 redirect. */
export async function logout() {
  await api.post('/auth/logout', null, { skipAuthRedirect: true });
}

// ---------- Two-step verification (6-digit email code) ----------
// /auth/register and /auth/login answer 202 { verification_required, purpose, email, sent_to, demo_code? }
// when a code was emailed. The code is then checked here; both return { access_token, expires_in, user }.

/** POST /api/auth/register/verify { email, code } -> 201 session (the new account is signed in) */
export async function verifyRegistration({ email, code }) {
  const { data } = await api.post(
    '/auth/register/verify',
    { email, code },
    { skipAuth: true, skipAuthRedirect: true },
  );
  return data;
}

/** POST /api/auth/login/verify { email, code } -> session */
export async function verifyLogin({ email, code }) {
  const { data } = await api.post('/auth/login/verify', { email, code }, { skipAuth: true, skipAuthRedirect: true });
  return data;
}

/** POST /api/auth/resend-code { email, purpose: 'register' | 'login' } -> 202 like above */
export async function resendCode({ email, purpose }) {
  const { data } = await api.post('/auth/resend-code', { email, purpose }, { skipAuth: true, skipAuthRedirect: true });
  return data;
}
