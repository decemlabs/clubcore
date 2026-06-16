/**
 * Attendance feature API hooks (Phase 103-02 — wire from mock to real).
 *
 * Delegates to features/visits hooks. This thin re-export layer lets
 * AttendancePage/CheckInModal import from @/features/attendance/api without
 * knowing the visits domain key structure directly (ESLint boundary).
 *
 * useCheckIn and useGymMeta re-exported so CheckInModal only needs one import.
 */
export {
  useVisitsList as useAttendanceList,
  useCheckIn,
  useGymMeta,
} from '@/features/visits/api';
export { visitsKeys as attendanceVisitsKeys } from '@/features/visits/api';
export { ApiError } from '@/features/visits/api';
