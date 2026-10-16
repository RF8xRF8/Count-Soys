// 后端所有时间都按北京时间（UTC+8）返回，且是不带时区的 ISO 字符串
// （形如 2026-10-10T09:30:00.123456）。这里只做展示格式化，不做时区换算，
// 这样无论设备处于哪个时区，显示的都是同一个北京时间。

export const formatTime = value => {
  if (!value) return '-'
  const [date, time = ''] = String(value).replace('T', ' ').split(' ')
  const clock = time.split('.')[0].slice(0, 8)
  return clock ? `${date} ${clock}` : date
}
