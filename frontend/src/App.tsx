import React from 'react';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center">
      <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-2xl flex items-center justify-center font-black text-2xl mb-4 shadow-sm">
        FS
      </div>
      <h1 className="text-3xl font-extrabold text-slate-900 mb-2">
        Bharat FoodSafe
      </h1>
      <p className="text-slate-600 max-w-md mb-6">
        Digital Food-Safety Operational Assurance & Compliance Platform. Initial project foundation established.
      </p>
      <div className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-700 rounded-full text-xs font-bold border border-emerald-200">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        Step 1.1 Foundation Initialized
      </div>
    </div>
  );
};

export default App;
