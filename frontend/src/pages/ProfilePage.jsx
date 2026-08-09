import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'
import { IconUser, IconLock, IconCheckCircle, IconAlertTriangle, IconActivity } from '../components/Icons'

const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }

export default function ProfilePage() {
  const { user, updateProfile, updatePassword } = useAuth()
  
  // Profile State
  const [profileForm, setProfileForm] = useState({
    full_name: '',
    dob: '',
    gender: '',
    state: ''
  })
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileStatus, setProfileStatus] = useState(null)
  
  // Password State
  const [pwdForm, setPwdForm] = useState({
    newPassword: '',
    confirmPassword: ''
  })
  const [pwdLoading, setPwdLoading] = useState(false)
  const [pwdStatus, setPwdStatus] = useState(null)

  // Load existing metadata
  useEffect(() => {
    if (user?.user_metadata) {
      setProfileForm({
        full_name: user.user_metadata.full_name || '',
        dob: user.user_metadata.dob || '',
        gender: user.user_metadata.gender || '',
        state: user.user_metadata.state || ''
      })
    }
  }, [user])

  // Calculate age dynamically
  const calculateAge = (dobString) => {
    if (!dobString) return null
    const birthDate = new Date(dobString)
    const today = new Date()
    let age = today.getFullYear() - birthDate.getFullYear()
    const m = today.getMonth() - birthDate.getMonth()
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
      age--
    }
    return age
  }

  const age = calculateAge(profileForm.dob)

  const handleProfileSubmit = async (e) => {
    e.preventDefault()
    setProfileLoading(true)
    setProfileStatus(null)

    try {
      await updateProfile({
        full_name: profileForm.full_name,
        dob: profileForm.dob,
        gender: profileForm.gender,
        state: profileForm.state
      })
      setProfileStatus({ type: 'success', message: 'Profile updated successfully!' })
      setTimeout(() => setProfileStatus(null), 3000)
    } catch (err) {
      setProfileStatus({ type: 'error', message: err.message || 'Failed to update profile.' })
    } finally {
      setProfileLoading(false)
    }
  }

  const handlePasswordSubmit = async (e) => {
    e.preventDefault()
    setPwdLoading(true)
    setPwdStatus(null)

    if (pwdForm.newPassword.length < 6) {
      setPwdStatus({ type: 'error', message: 'Password must be at least 6 characters.' })
      setPwdLoading(false)
      return
    }

    if (pwdForm.newPassword !== pwdForm.confirmPassword) {
      setPwdStatus({ type: 'error', message: 'Passwords do not match.' })
      setPwdLoading(false)
      return
    }

    try {
      await updatePassword(pwdForm.newPassword)
      setPwdStatus({ type: 'success', message: 'Password updated successfully!' })
      setPwdForm({ newPassword: '', confirmPassword: '' })
      setTimeout(() => setPwdStatus(null), 3000)
    } catch (err) {
      setPwdStatus({ type: 'error', message: err.message || 'Failed to update password.' })
    } finally {
      setPwdLoading(false)
    }
  }

  return (
    <section className="section-white section-pad">
      <div className="main" style={{ maxWidth: '800px', margin: '0 auto' }}>
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.1 } } }}>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title" style={{ marginBottom: '0.5rem' }}>
            Account <span className="gradient-text">Profile</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.5 }} className="section-subtitle" style={{ marginBottom: '2.5rem', textAlign: 'left' }}>
            Manage your personal information and security settings.
          </motion.p>
        </motion.div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* ── Personal Information Card ──────────────────────────────── */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }} className="card" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
              <div className="feature-icon red"><IconUser size={20} /></div>
              <div>
                <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>Personal Information</h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Used to contextualize claim evaluations.</p>
              </div>
            </div>

            <form onSubmit={handleProfileSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Email Address</label>
                <input className="input" value={user?.email || ''} disabled style={{ background: 'var(--bg-secondary)', color: 'var(--text-tertiary)', cursor: 'not-allowed' }} />
                <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>Your email address cannot be changed.</p>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Full Name</label>
                <input className="input" value={profileForm.full_name} onChange={e => setProfileForm({...profileForm, full_name: e.target.value})} placeholder="John Doe" required />
              </div>

              <div className="grid-2">
                <div>
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Date of Birth</label>
                  <input type="date" className="input" value={profileForm.dob} onChange={e => setProfileForm({...profileForm, dob: e.target.value})} />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Current Age</label>
                  <div style={{ padding: '0.75rem 1rem', background: 'var(--bg-secondary)', borderRadius: '0.5rem', border: '1px solid var(--border-secondary)', fontSize: '0.9375rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                    {age !== null && !isNaN(age) ? `${age} years old` : '—'}
                  </div>
                </div>
              </div>

              <div className="grid-2">
                <div>
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Gender</label>
                  <select className="input" value={profileForm.gender} onChange={e => setProfileForm({...profileForm, gender: e.target.value})}>
                    <option value="">Select Gender...</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Non-Binary">Non-Binary</option>
                    <option value="Prefer not to say">Prefer not to say</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>State of Residence</label>
                  <select className="input" value={profileForm.state} onChange={e => setProfileForm({...profileForm, state: e.target.value})}>
                    <option value="">Select State...</option>
                    <option value="AL">Alabama</option><option value="AK">Alaska</option><option value="AZ">Arizona</option><option value="AR">Arkansas</option><option value="CA">California</option><option value="CO">Colorado</option><option value="CT">Connecticut</option><option value="DE">Delaware</option><option value="FL">Florida</option><option value="GA">Georgia</option><option value="HI">Hawaii</option><option value="ID">Idaho</option><option value="IL">Illinois</option><option value="IN">Indiana</option><option value="IA">Iowa</option><option value="KS">Kansas</option><option value="KY">Kentucky</option><option value="LA">Louisiana</option><option value="ME">Maine</option><option value="MD">Maryland</option><option value="MA">Massachusetts</option><option value="MI">Michigan</option><option value="MN">Minnesota</option><option value="MS">Mississippi</option><option value="MO">Missouri</option><option value="MT">Montana</option><option value="NE">Nebraska</option><option value="NV">Nevada</option><option value="NH">New Hampshire</option><option value="NJ">New Jersey</option><option value="NM">New Mexico</option><option value="NY">New York</option><option value="NC">North Carolina</option><option value="ND">North Dakota</option><option value="OH">Ohio</option><option value="OK">Oklahoma</option><option value="OR">Oregon</option><option value="PA">Pennsylvania</option><option value="RI">Rhode Island</option><option value="SC">South Carolina</option><option value="SD">South Dakota</option><option value="TN">Tennessee</option><option value="TX">Texas</option><option value="UT">Utah</option><option value="VT">Vermont</option><option value="VA">Virginia</option><option value="WA">Washington</option><option value="WV">West Virginia</option><option value="WI">Wisconsin</option><option value="WY">Wyoming</option>
                  </select>
                </div>
              </div>

              {profileStatus && (
                <div style={{ padding: '0.75rem 1rem', borderRadius: '0.5rem', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: profileStatus.type === 'success' ? 'var(--success-bg)' : 'var(--danger-bg)', color: profileStatus.type === 'success' ? 'var(--success)' : 'var(--danger)', border: `1px solid ${profileStatus.type === 'success' ? '#a7f3d0' : '#fecaca'}` }}>
                  {profileStatus.type === 'success' ? <IconCheckCircle size={16} /> : <IconAlertTriangle size={16} />}
                  {profileStatus.message}
                </div>
              )}

              <button type="submit" className="btn btn-red" disabled={profileLoading} style={{ alignSelf: 'flex-start' }}>
                {profileLoading ? <><span className="spinner" /> Saving...</> : 'Save Changes'}
              </button>
            </form>
          </motion.div>

          {/* ── Security Card ──────────────────────────────────────────── */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.3 }} className="card" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
              <div className="feature-icon" style={{ background: '#f3f4f6', color: '#4b5563' }}><IconLock size={20} /></div>
              <div>
                <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>Security</h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Update your account password.</p>
              </div>
            </div>

            <form onSubmit={handlePasswordSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>New Password</label>
                <input type="password" className="input" value={pwdForm.newPassword} onChange={e => setPwdForm({...pwdForm, newPassword: e.target.value})} placeholder="Minimum 6 characters" required minLength={6} />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Confirm New Password</label>
                <input type="password" className="input" value={pwdForm.confirmPassword} onChange={e => setPwdForm({...pwdForm, confirmPassword: e.target.value})} placeholder="Re-enter password" required minLength={6} />
              </div>

              {pwdStatus && (
                <div style={{ padding: '0.75rem 1rem', borderRadius: '0.5rem', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: pwdStatus.type === 'success' ? 'var(--success-bg)' : 'var(--danger-bg)', color: pwdStatus.type === 'success' ? 'var(--success)' : 'var(--danger)', border: `1px solid ${pwdStatus.type === 'success' ? '#a7f3d0' : '#fecaca'}` }}>
                  {pwdStatus.type === 'success' ? <IconCheckCircle size={16} /> : <IconAlertTriangle size={16} />}
                  {pwdStatus.message}
                </div>
              )}

              <button type="submit" className="btn btn-outline" disabled={pwdLoading} style={{ alignSelf: 'flex-start' }}>
                {pwdLoading ? <><span className="spinner" /> Updating...</> : 'Update Password'}
              </button>
            </form>
          </motion.div>

        </div>
      </div>
    </section>
  )
}
