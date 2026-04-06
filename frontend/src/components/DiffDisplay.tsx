import React from 'react';

interface DiffItem {
  original: string;
  modified: string;
  label: string;
}

interface SkillChange {
  added: string[];
  removed: string[];
}

interface MetricsChange {
  metric: string;
  original: number | string;
  modified: number | string;
  change?: number | string;
}

interface DiffDisplayProps {
  title: string;
  changes?: DiffItem[];
  skillChanges?: SkillChange;
  metricsChanges?: MetricsChange[];
  summary?: {
    totalChanges: number;
    addedItems: number;
    removedItems: number;
  };
}

const DiffDisplay: React.FC<DiffDisplayProps> = ({
  title,
  changes,
  skillChanges,
  metricsChanges,
  summary,
}) => {
  const formatChange = (value: number | string): string => {
    if (typeof value === 'number') {
      return value.toFixed(2);
    }
    return String(value);
  };

  const calculateChangePercent = (original: number, modified: number): string => {
    if (original === 0) return '∞';
    const percent = ((modified - original) / original) * 100;
    return percent > 0 ? `+${percent.toFixed(1)}%` : `${percent.toFixed(1)}%`;
  };

  return (
    <div className="diff-container">
      <div className="diff-section">
        <h4>📋 {title}</h4>

        {/* Changes Section */}
        {changes && changes.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <p className="diff-meta">Text Changes ({changes.length})</p>
            {changes.map((change, idx) => (
              <div key={idx} className="skills-change">
                <strong className="diff-label">{change.label}</strong>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '8px' }}>
                  <div>
                    <p style={{ fontSize: '0.75rem', color: 'var(--muted)', marginBottom: '4px' }}>Original</p>
                    <p style={{
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      padding: '8px',
                      borderRadius: 'var(--radius)',
                      color: 'var(--danger)',
                      fontSize: '0.85rem',
                      margin: '0',
                      wordBreak: 'break-word',
                    }}>
                      {change.original}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: '0.75rem', color: 'var(--muted)', marginBottom: '4px' }}>Modified</p>
                    <p style={{
                      background: 'rgba(16, 185, 129, 0.1)',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      padding: '8px',
                      borderRadius: 'var(--radius)',
                      color: 'var(--success)',
                      fontSize: '0.85rem',
                      margin: '0',
                      wordBreak: 'break-word',
                    }}>
                      {change.modified}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Skills Changes Section */}
        {skillChanges && (skillChanges.added?.length > 0 || skillChanges.removed?.length > 0) && (
          <div style={{ marginTop: '16px' }}>
            <p className="diff-meta">Skills Changes</p>

            {skillChanges.added && skillChanges.added.length > 0 && (
              <div className="skills-change added">
                <strong>✅ Skills Added ({skillChanges.added.length})</strong>
                <div className="skills-list">
                  {skillChanges.added.map((skill, idx) => (
                    <span key={idx} className="skill-tag-added">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {skillChanges.removed && skillChanges.removed.length > 0 && (
              <div className="skills-change removed">
                <strong>❌ Skills Removed ({skillChanges.removed.length})</strong>
                <div className="skills-list">
                  {skillChanges.removed.map((skill, idx) => (
                    <span key={idx} className="skill-tag-removed">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Metrics Changes Section */}
        {metricsChanges && metricsChanges.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <p className="diff-meta">Metrics Changes</p>
            <table className="diff-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Original</th>
                  <th>Modified</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {metricsChanges.map((metric, idx) => {
                  const isNumeric = typeof metric.original === 'number' && typeof metric.modified === 'number';
                  const changeValue = isNumeric ? calculateChangePercent(metric.original as number, metric.modified as number) : metric.change || '—';
                  const isPositiveChange = isNumeric && (metric.modified as number) > (metric.original as number);

                  return (
                    <tr key={idx}>
                      <td>{metric.metric}</td>
                      <td>{formatChange(metric.original)}</td>
                      <td>{formatChange(metric.modified)}</td>
                      <td className={isPositiveChange ? 'positive' : 'negative'}>
                        {changeValue}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Summary Section */}
        {summary && (
          <div className="diff-summary">
            <div className="summary-item">
              <span>📊 Total Changes:</span>
              <strong>{summary.totalChanges}</strong>
            </div>
            <div className="summary-item">
              <span>✅ Added:</span>
              <strong style={{ color: 'var(--success)' }}>{summary.addedItems}</strong>
            </div>
            <div className="summary-item">
              <span>❌ Removed:</span>
              <strong style={{ color: 'var(--danger)' }}>{summary.removedItems}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DiffDisplay;
