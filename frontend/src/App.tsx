import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Studio } from './pages/Studio'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Studio />} />
      </Routes>
    </Router>
  )
}

export default App
