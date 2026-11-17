// Step 2 of sign-in / sign-up: type the 6-digit code that was emailed (two-step verification).
// `verification` is the server's 202 answer: { purpose, email, sent_to, message, demo_code? }.
import { useEffect, useState } from 'react';
import { resendCode } from '../api/auth';
import { getApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';

const RESEND_WAIT_SECONDS = 30;

export default function VerificationCodeStep({ verification, onVerified, onBack }) {
  const { verifyCode } = useAuth();
  const [info, setInfo] = useState(verification);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(RESEND_WAIT_SECONDS);

  // Count down before "Resend code" can be used again.
  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = window.setTimeout(() => setWait((w) => w - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  const submit = async (event) => {
    event.preventDefault();
    if (!/^\d{6}$/.test(code.trim())) {
      setError('Enter the 6-digit code from the email.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const user = await verifyCode({ purpose: info.purpose, email: info.email, code });
      onVerified(user);
    } catch (err) {
      setError(getApiError(err).message);
      setBusy(false);
    }
  };

  const resend = async () => {
    setError('');
    try {
      const data = await resendCode({ email: info.email, purpose: info.purpose });
      setInfo(data);
      setCode('');
      setWait(RESEND_WAIT_SECONDS);
    } catch (err) {
      setError(getApiError(err).message);
    }
  };

  return (
    <form onSubmit={submit} noValidate aria-label="Verification code form">
      <div className="text-center mb-4">
        <span className="fa-icon-tile fa-tone-teal fa-icon-tile-lg mx-auto mb-2" aria-hidden="true">
          <i className="bi bi-shield-lock" />
        </span>
        <p className="small text-muted mb-0">
          {info.purpose === 'register' ? 'To confirm your email address, we' : 'For your security, we'} sent a 6-digit
          code to <strong className="text-body">{info.sent_to || info.email}</strong>.
        </p>
      </div>

      {info.demo_code && (
        <div className="alert alert-info small d-flex align-items-center gap-2" role="status">
          <i className="bi bi-info-circle-fill" aria-hidden="true" />
          <span className="flex-grow-1">
            Demo mode (no email server set up). Your code is <strong className="fa-otp-demo">{info.demo_code}</strong>
          </span>
          <button type="button" className="btn btn-sm btn-light" onClick={() => setCode(info.demo_code)}>
            Use it
          </button>
        </div>
      )}

      {error && (
        <div className="alert alert-danger d-flex gap-2 small" role="alert">
          <i className="bi bi-exclamation-circle-fill" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <label htmlFor="otp-code" className="form-label">
        Verification code
      </label>
      <input
        id="otp-code"
        className="form-control form-control-lg text-center fa-otp-input mb-3"
        value={code}
        onChange={(e) => {
          setCode(e.target.value.replace(/\D/g, '').slice(0, 6));
          setError('');
        }}
        inputMode="numeric"
        autoComplete="one-time-code"
        placeholder="••••••"
        autoFocus
      />

      <button type="submit" className="btn btn-primary fa-btn-gradient w-100 py-2" disabled={busy}>
        {busy && <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />}
        {info.purpose === 'register' ? 'Verify and create account' : 'Verify and sign in'}
      </button>

      <div className="d-flex justify-content-between align-items-center small mt-3">
        <button type="button" className="btn btn-link btn-sm p-0" onClick={onBack} disabled={busy}>
          <i className="bi bi-arrow-left me-1" aria-hidden="true" />
          Back
        </button>
        <button type="button" className="btn btn-link btn-sm p-0" onClick={resend} disabled={busy || wait > 0}>
          {wait > 0 ? `Resend code in ${wait}s` : 'Resend code'}
        </button>
      </div>
    </form>
  );
}
