import { useState } from 'react';
import { useAppStore } from '../../store/index';
import type { UseCase, PrivacyLevel } from '../../types/index';

export function ContextForm(): JSX.Element {
  const [dataDictFile, setDataDictFile] = useState<string | null>(null);
  const [sampleDataFile, setSampleDataFile] = useState<string | null>(null);
  const [tablesInScope, setTablesInScope] = useState<string>('');

  const {
    context,
    setContext,
  } = useAppStore();

  const handleObjectiveChange = (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
    setContext({ objective: e.target.value });
  };

  const handleUseCaseChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    setContext({ useCase: e.target.value as UseCase });
  };

  const handleDataDictUpload = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const filename = e.target.files?.[0]?.name ?? null;
    setDataDictFile(filename);
  };

  const handleSampleDataUpload = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const filename = e.target.files?.[0]?.name ?? null;
    setSampleDataFile(filename);
  };

  const handleTablesInScopeChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    setTablesInScope(e.target.value);
  };

  const handleOutputSizeChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value)) {
      setContext({ targetRowCounts: { _default: value } });
    }
  };

  const handlePrivacyLevelChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    setContext({ privacyLevel: e.target.value as PrivacyLevel });
  };

  const handleScenarioChange = (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
    setContext({ scenarioDescription: e.target.value });
  };

  const handleConstraintsChange = (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
    setContext({ additionalConstraints: e.target.value });
  };

  return (
    <form className="space-y-4">
      {/* 1. Primary objective */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Primary objective
        </label>
        <textarea
          value={context.objective}
          onChange={handleObjectiveChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
          placeholder="Describe the primary objective..."
        />
      </div>

      {/* 2. Downstream use */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Downstream use
        </label>
        <select
          value={context.useCase}
          onChange={handleUseCaseChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="ml_training">ML Training</option>
          <option value="analytics">Analytics</option>
          <option value="qa_testing">QA Testing</option>
          <option value="regulatory">Regulatory</option>
        </select>
      </div>

      {/* 3. Data dictionary upload */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Data dictionary upload
        </label>
        <input
          type="file"
          accept=".txt,.sql,.csv"
          onChange={handleDataDictUpload}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
        />
        {dataDictFile && (
          <p className="text-xs text-gray-500 mt-1">File: {dataDictFile}</p>
        )}
      </div>

      {/* 4. Sample data upload */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Sample data upload
        </label>
        <input
          type="file"
          accept=".csv"
          onChange={handleSampleDataUpload}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
        />
        {sampleDataFile && (
          <p className="text-xs text-gray-500 mt-1">File: {sampleDataFile}</p>
        )}
      </div>

      {/* 5. Tables in scope */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Tables in scope
        </label>
        <input
          type="text"
          value={tablesInScope}
          onChange={handleTablesInScopeChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Comma-separated table names..."
        />
      </div>

      {/* 6. Output size (rows) */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Output size (rows)
        </label>
        <input
          type="number"
          min="100"
          max="10000000"
          onChange={handleOutputSizeChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="1000"
        />
      </div>

      {/* 7. Privacy requirement */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Privacy requirement
        </label>
        <select
          value={context.privacyLevel}
          onChange={handlePrivacyLevelChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="none">None</option>
          <option value="no_verbatim_pii">No verbatim PII</option>
          <option value="k5">k=5</option>
          <option value="k10">k=10</option>
        </select>
      </div>

      {/* 8. Scenario description */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Scenario description
        </label>
        <textarea
          value={context.scenarioDescription}
          onChange={handleScenarioChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
          placeholder="Describe the scenario..."
        />
      </div>

      {/* 9. Additional constraints */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Additional constraints
        </label>
        <textarea
          value={context.additionalConstraints}
          onChange={handleConstraintsChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
          placeholder="Any additional constraints..."
        />
      </div>
    </form>
  );
}
