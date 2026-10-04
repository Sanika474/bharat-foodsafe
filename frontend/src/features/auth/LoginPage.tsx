import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, UserCheck, Shield } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

type LoginMode = 'staff' | 'admin';

export const LoginPage: React.FC = () => {
  const { login, authError, clearError } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<LoginMode>('staff');
  const [phone, setPhone] = useState('');
  const [pin, setPin] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleModeSwitch = (newMode: LoginMode) => {
    setMode(newMode);
    setFormError(null);
    clearError();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    clearError();

    if (mode === 'staff') {
      const cleanedPhone = phone.replace(/\D/g, '');
      if (cleanedPhone.length !== 10) {
        setFormError('Please enter a valid 10-digit mobile phone number.');
        return;
      }
      if (!pin || pin.length < 4 || pin.length > 6 || !/^\d+$/.test(pin)) {
        setFormError('Please enter a valid 4 to 6 digit security PIN.');
        return;
      }

      setIsSubmitting(true);
      try {
        const user = await login({ phone: cleanedPhone, pin });
        redirectUser(user.roles);
      } catch {
        // Handled via authError state in AuthContext
      } finally {
        setIsSubmitting(false);
      }
    } else {
      if (!email || !email.includes('@')) {
        setFormError('Please enter a valid email address.');
        return;
      }
      if (!password || password.length < 6) {
        setFormError('Please enter your admin password.');
        return;
      }

      setIsSubmitting(true);
      try {
        const user = await login({ email, password });
        redirectUser(user.roles);
      } catch {
        // Handled via authError
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const redirectUser = (roles: string[]) => {
    if (roles.includes('STAFF')) {
      navigate('/staff/dashboard', { replace: true });
    } else if (roles.includes('MANAGER')) {
      navigate('/manager/dashboard', { replace: true });
    } else if (roles.includes('PLATFORM_ADMIN')) {
      navigate('/admin/dashboard', { replace: true });
    } else {
      navigate('/staff/dashboard', { replace: true });
    }
  };

  const activeError = formError || authError;

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center items-center p-4 sm:p-6 text-slate-100">
      <div className="w-full max-w-md bg-white text-slate-900 rounded-3xl shadow-2xl overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        {/* Brand Header */}
        <div className="bg-emerald-600 p-6 sm:p-8 text-center text-white flex flex-col items-center gap-2">
          <div className="w-14 h-14 bg-white/10 rounded-2xl flex items-center justify-center backdrop-blur-md shadow-inner">
            <ShieldCheck className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-black tracking-tight">Bharat FoodSafe</h1>
          <p className="text-emerald-100 text-xs sm:text-sm font-medium">
            Digital Food-Safety Operational Assurance
          </p>
        </div>

        {/* Mode Selector Tabs */}
        <div className="flex border-b border-slate-200 bg-slate-50 p-1.5 gap-1">
          <button
            type="button"
            onClick={() => handleModeSwitch('staff')}
            className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-bold text-xs sm:text-sm transition-all min-h-[48px] ${
              mode === 'staff'
                ? 'bg-white text-emerald-700 shadow-sm border border-slate-200'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <UserCheck className="w-4 h-4" />
            Kitchen Staff / Manager
          </button>
          <button
            type="button"
            onClick={() => handleModeSwitch('admin')}
            className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-bold text-xs sm:text-sm transition-all min-h-[48px] ${
              mode === 'admin'
                ? 'bg-white text-emerald-700 shadow-sm border border-slate-200'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Shield className="w-4 h-4" />
            Platform Admin
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 sm:p-8 flex flex-col gap-5">
          {activeError && (
            <Alert variant="error" title="Authentication Error" message={activeError} />
          )}

          {mode === 'staff' ? (
            <>
              <Input
                label="Mobile Phone Number"
                id="phone"
                type="tel"
                placeholder="10-digit mobile number"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                disabled={isSubmitting}
                maxLength={10}
                required
              />
              <Input
                label="Security PIN"
                id="pin"
                type="password"
                placeholder="4 to 6 digit PIN"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                disabled={isSubmitting}
                maxLength={6}
                required
              />
            </>
          ) : (
            <>
              <Input
                label="Admin Email Address"
                id="email"
                type="email"
                placeholder="admin@bharatfoodsafe.io"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSubmitting}
                required
              />
              <Input
                label="Password"
                id="password"
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            isLoading={isSubmitting}
            className="w-full mt-2"
          >
            {mode === 'staff' ? 'Sign In with Phone & PIN' : 'Sign In as Admin'}
          </Button>

          <p className="text-center text-xs text-slate-400 mt-2">
            Protected by multi-tenant session isolation and AES/bcrypt security standards.
          </p>
        </form>
      </div>
    </div>
  );
};
