export default function Spinner({ size = 'h-8 w-8' }) {
  return (
    <div className={`animate-spin rounded-full ${size} border-b-2 border-premier-700`}></div>
  );
}
