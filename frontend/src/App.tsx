import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<div className="p-8">Welcome to synth-data-studio</div>} />
      </Routes>
    </Router>
  )
}

export default App
