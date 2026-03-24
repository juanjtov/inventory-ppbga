export default function StockBadge({ product }) {
  if (product.type === 'service') {
    return <span className="bg-blue-100 text-blue-700 px-2.5 py-0.5 rounded-full text-xs font-medium">Servicio</span>;
  }
  if (product.stock === 0) {
    return <span className="bg-red-100 text-red-700 px-2.5 py-0.5 rounded-full text-xs font-medium">Agotado</span>;
  }
  if (product.is_low_stock) {
    return <span className="bg-yellow-100 text-yellow-700 px-2.5 py-0.5 rounded-full text-xs font-medium">Bajo</span>;
  }
  return <span className="bg-green-100 text-green-700 px-2.5 py-0.5 rounded-full text-xs font-medium">OK</span>;
}
