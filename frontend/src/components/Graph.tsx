// @ts-nocheck
import CytoscapeComponent from 'react-cytoscapejs';
import type { GraphEl } from '../api';

const STYLE = [
  { selector: 'node', style: {
      label: 'data(label)', 'text-valign': 'center', 'text-halign': 'center',
      'text-wrap': 'wrap', 'text-max-width': '130px', 'font-size': '11px',
      shape: 'round-rectangle', width: '150px', height: '46px',
      'background-color': '#f3f5f7', 'border-color': '#b6c0ca', 'border-width': 1.5,
      color: '#17212f' } },
  { selector: 'node[kind="derived"]', style: {
      'background-color': '#d8eafa', 'border-color': '#82add6' } },
  { selector: 'node[priority="regulatory"]', style: {
      'background-color': '#fdeccd', 'border-color': '#e0a94a' } },
  { selector: 'edge', style: {
      label: 'data(label)', 'font-size': '9px', color: '#5a6b7f',
      'text-background-color': '#fff', 'text-background-opacity': 1, 'text-background-padding': '2px',
      width: 1.5, 'line-color': '#8aa0b6', 'target-arrow-color': '#8aa0b6',
      'target-arrow-shape': 'triangle', 'curve-style': 'bezier' } },
  { selector: 'edge[lag >= 1]', style: {
      'line-color': '#7a56b0', 'target-arrow-color': '#7a56b0' } },
];

export function Graph({ elements }: { elements: GraphEl[] }) {
  if (!elements.length) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">
      The design graph appears here as you answer.
    </div>;
  }
  // key forces a re-layout when the set of elements changes
  const key = elements.map((e) => e.data.id).join('|');
  return (
    <CytoscapeComponent
      key={key}
      elements={elements as any}
      layout={{ name: 'breadthfirst', directed: true, spacingFactor: 1.35, padding: 24 }}
      stylesheet={STYLE as any}
      style={{ width: '100%', height: '100%' }}
    />
  );
}
