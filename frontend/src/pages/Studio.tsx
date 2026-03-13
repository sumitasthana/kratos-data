import { useState } from 'react';

type TabName = 'Chat' | 'Schema' | 'Profile' | 'Rules' | 'Output' | 'Validation' | 'Logs';

interface TabConfig {
  name: TabName;
  phase: number;
}

const TABS: TabConfig[] = [
  { name: 'Chat', phase: 5 },
  { name: 'Schema', phase: 6 },
  { name: 'Profile', phase: 10 },
  { name: 'Rules', phase: 7 },
  { name: 'Output', phase: 8 },
  { name: 'Validation', phase: 9 },
  { name: 'Logs', phase: 11 },
];

export function Studio(): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabName>('Chat');

  const renderTabContent = (): JSX.Element => {
    const tab = TABS.find((t) => t.name === activeTab);
    if (!tab) {
      return <div>Unknown tab</div>;
    }
    return (
      <div className="p-6 text-gray-600">
        {tab.name} — Phase {tab.phase}
      </div>
    );
  };

  return (
    <div className="h-screen flex overflow-hidden bg-white">
      {/* Left Panel */}
      <div className="w-80 border-r border-gray-200 flex flex-col bg-gray-50">
        {/* App Title / Logo */}
        <div className="p-6 border-b border-gray-200">
          <h1 className="text-xl font-bold text-gray-900">synth-data-studio</h1>
        </div>

        {/* Context Form Area */}
        <div className="flex-1 p-6 border-b border-gray-200 overflow-y-auto">
          <div className="text-gray-600">Context Form — Phase 3</div>
        </div>

        {/* Chat Terminal Area */}
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="text-gray-600">Chat Terminal — Phase 5</div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tab Bar */}
        <div className="border-b border-gray-200 bg-white">
          <div className="flex">
            {TABS.map((tab) => (
              <button
                key={tab.name}
                onClick={() => setActiveTab(tab.name)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.name
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                {tab.name}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content Area */}
        <div className="flex-1 overflow-hidden bg-white">
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
}
