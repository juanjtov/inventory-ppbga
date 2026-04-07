import { useEffect } from 'react';
import { X } from 'lucide-react';

export default function Modal({ isOpen, onClose, title, children, maxWidth = 'max-w-lg' }) {
  useEffect(() => {
    if (isOpen) {
      console.log('[Modal] mounted', { title, time: performance.now() });
      return () => console.log('[Modal] unmounted', { title, time: performance.now() });
    }
  }, [isOpen, title]);

  if (!isOpen) return null;

  const handleBackdropClick = (e) => {
    console.log('[Modal] backdrop click', {
      title,
      target: e.target.tagName,
      currentTarget: e.currentTarget.tagName,
      sameAsCurrent: e.target === e.currentTarget,
      time: performance.now(),
    });
    onClose(e);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={handleBackdropClick}>
      <div
        className={`bg-white rounded-2xl shadow-xl ${maxWidth} w-full mx-4 p-6`}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <button
            onClick={() => { console.log('[Modal] X button clicked', { title, time: performance.now() }); onClose(); }}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
