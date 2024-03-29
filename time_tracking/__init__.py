#!/usr/bin/env python3
import argparse
import calendar
import datetime
import itertools
import operator
import os.path
import sys
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

import docutils.core
import ibis
import ibis.errors
import ibis.filters
import ibis.loaders
import ibis.nodes
import yaml
from ibis.compiler import Token


T = TypeVar('T')


def previous_and_next(
    some_iterable: Iterable[T]
) -> Iterable[Tuple[Optional[T], T, Optional[T]]]:
    prevs_temp, items, nexts_temp = itertools.tee(some_iterable, 3)
    none = cast(List[T], [None])
    prevs = itertools.chain(none, prevs_temp)
    nexts = itertools.chain(itertools.islice(nexts_temp, 1, None), none)
    return zip(prevs, items, nexts)


@ibis.filters.register('dformat')
def delta_formatter(delta: datetime.timedelta, delta_format: str = 'hh:mm') -> str:
    if isinstance(delta, ibis.errors.UndefinedVariable):
        return ''
    if delta_format == "decimal":
        return delta_to_decimal(delta)
    elif delta_format == "hh:mm":
        return delta_to_hhmm(delta)
    elif delta_format == "text":
        return delta_to_text(delta)
    else:
        assert False


@ibis.filters.register('round_delta')
def delta_formatter_round(delta: datetime.timedelta, period: str = 'hh:mm') -> datetime.timedelta:
    period_delta = parse_delta(period)
    return round_timedelta(delta, period_delta)


@ibis.nodes.register('add_delta', None)
class AddDelta(ibis.nodes.Node):
    def process_token(self, token: Token) -> None:
        tag, total, value = token.content.split(None, 2)
        self.total = ibis.nodes.Expression(total)
        self.value = ibis.nodes.Expression(value)

    def render(self, context: Any) -> str:
        total = self.total.eval(context)
        value = self.value.eval(context)

        if total in context:
            result = context[total]
        else:
            result = datetime.timedelta()

        result = result + value
        context.stack[0][total] = result

        content = super().render(context)
        return content


@ibis.filters.register('rst')
def rst_formatter(text: str) -> str:
    if text is None:
        return ""
    return docutils.core.publish_parts(text, writer_name='html')['html_body']


@ibis.nodes.register('rst_l1_header', 'end_rst_l1_header')
class RstL1Header(ibis.nodes.Node):
    def render(self, context: Any) -> str:
        content = super().render(context).replace('\n', '')
        result = [
            "="*len(content),
            content,
            "="*len(content),
        ]
        return "\n".join(result)


@ibis.nodes.register('rst_l2_header', 'end_rst_l2_header')
class RstL2Header(ibis.nodes.Node):
    def render(self, context: Any) -> str:
        content = super().render(context).replace('\n', '')
        result = [
            content,
            "-"*len(content),
        ]
        return "\n".join(result)


@ibis.nodes.register('rst_l3_header', 'end_rst_l3_header')
class RstL3Header(ibis.nodes.Node):
    def render(self, context: Any) -> str:
        content = super().render(context).replace('\n', '')
        result = [
            content,
            "~"*len(content),
        ]
        return "\n".join(result)


def parse_date(string: str) -> datetime.date:
    yyyy, mm, dd = string.split("-", maxsplit=3)
    return datetime.date(year=int(yyyy), month=int(mm), day=int(dd))


def parse_time(string: str) -> datetime.time:
    try:
        hh, mm = string.split(":", maxsplit=2)
    except Exception as e:
        raise RuntimeError(f"Error parsing {string}: {e}")
    return datetime.time(hour=int(hh), minute=int(mm))


def parse_datetime(string: str) -> datetime.datetime:
    date_str, time_str = string.split(" ", maxsplit=2)
    date = parse_date(date_str)
    time = parse_time(time_str)
    return datetime.datetime.combine(date, time)


def parse_delta(string: str) -> datetime.timedelta:
    hh, mm = string.split(":", maxsplit=2)
    return datetime.timedelta(hours=int(hh), minutes=int(mm))


def delta_to_decimal(delta: datetime.timedelta) -> str:
    days = delta.days
    return str(round(days * 24 + delta.seconds / 3600, 1))


def delta_to_hhmm(delta: datetime.timedelta) -> str:
    days = delta.days
    negative = "+"
    if days < 0:
        delta = -delta
        days = delta.days
        negative = "-"
    value, seconds = divmod(delta.seconds, 60)
    hours, minutes = divmod(value, 60)

    hh = hours + days*24
    mm = minutes
    return "%s%02d:%02d" % (negative, hh, mm)


def delta_to_text(delta: datetime.timedelta) -> str:
    days = delta.days
    negative = ""
    if days < 0:
        delta = -delta
        days = delta.days
        negative = "-"
    value, seconds = divmod(delta.seconds, 60)
    hours, minutes = divmod(value, 60)

    hh = hours + days*24
    mm = minutes

    result = []

    if hh == 1:
        result.append("%d hour" % hh)
    elif hh > 1:
        result.append("%d hours" % hh)

    if mm == 1:
        result.append("%d minute" % mm)
    if mm > 0:
        result.append("%d minutes" % mm)

    return negative + " and ".join(result)


def delta_to_format(delta: datetime.timedelta, delta_format: str) -> str:
    if delta_format == "decimal":
        return delta_to_decimal(delta)
    elif delta_format == "hh:mm":
        return delta_to_hhmm(delta)
    else:
        assert False


DateRange = Tuple[Optional[datetime.date], Optional[datetime.date]]


def add_months(date: datetime.date, months: int) -> datetime.date:
    month = date.month - 1 + months
    year = date.year + month // 12
    month = month % 12 + 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def get_date_range(date: datetime.date, day: bool, one: bool, two: bool, month: bool, financial_year: bool) -> DateRange:
    current_date = date

    start_date: Optional[datetime.date] = None
    stop_date: Optional[datetime.date] = None

    if day:
        start_date = current_date
        stop_date = current_date
    elif one:
        start_date = (
            current_date
            - datetime.timedelta(days=current_date.weekday())
        )
        stop_date = (
            current_date
            - datetime.timedelta(days=current_date.weekday())
            + datetime.timedelta(days=6)
        )
    elif two:
        start_date = (
            current_date
            - datetime.timedelta(days=current_date.weekday())
            - datetime.timedelta(days=7)
        )
        stop_date = (
            current_date
            - datetime.timedelta(days=current_date.weekday())
            + datetime.timedelta(days=6)
        )
    elif month:
        start_date = current_date.replace(day=1)
        stop_date = (
            add_months(current_date, 1).replace(day=1)
            - datetime.timedelta(days=1)
        )
    elif financial_year:
        if current_date.month < 7:
            start_date = current_date.replace(day=1, month=7, year=current_date.year-1)
        else:
            start_date = current_date.replace(day=1, month=7)

        stop_date = current_date.replace(
            day=30, month=6, year=start_date.year+1
        )

    return (start_date, stop_date)


def round_timedelta(td: datetime.timedelta, period: datetime.timedelta) -> datetime.timedelta:
    """
    Rounds the given timedelta by the given timedelta period
    :param td: `timedelta` to round
    :param period: `timedelta` period to round by.
    """
    period_seconds = period.total_seconds()
    half_period_seconds = period_seconds / 2
    remainder = td.total_seconds() % period_seconds
    if remainder >= half_period_seconds:
        return datetime.timedelta(
            seconds=td.total_seconds() + (period_seconds - remainder))
    else:
        return datetime.timedelta(
            seconds=td.total_seconds() - remainder)


class Entry:
    def __init__(
            self, *,
            task: 'Task',
            date: datetime.date, text: str,
            start_time: datetime.time, stop_time: datetime.time,
            break_delta: datetime.timedelta, t_raw_delta: datetime.timedelta,
            round_delta: datetime.timedelta, total_delta: datetime.timedelta) -> None:
        self.task = task
        self.date = date
        self.text = text
        self.start_time = start_time
        self.stop_time = stop_time
        self.break_delta = break_delta
        self.t_raw_delta = t_raw_delta
        self.round_delta = round_delta
        self.total_delta = total_delta


class AggregatedTextEntry:
    def __init__(
            self, *,
            task: 'Task', text: str,
            total_delta: datetime.timedelta) -> None:
        self.task = task
        self.text = text
        self.total_delta = total_delta


class AggregatedDay:
    def __init__(
            self, *, date: datetime.date,
            total_delta: datetime.timedelta) -> None:
        self.date = date
        self.total_delta = total_delta


class AggregatedEmployer:
    def __init__(
            self, *, date: datetime.date,
            total_delta: datetime.timedelta,
            employer: 'Employer') -> None:
        self.date = date
        self.total_delta = total_delta
        self.employer = employer


class AggregatedProject:
    def __init__(
            self, *, date: datetime.date,
            total_delta: datetime.timedelta,
            project: 'Project') -> None:
        self.date = date
        self.total_delta = total_delta
        self.project = project


class AggregatedTask:
    def __init__(
            self, *, date: datetime.date,
            total_delta: datetime.timedelta,
            task: 'Task') -> None:
        self.date = date
        self.total_delta = total_delta
        self.task = task


class EntryList:
    def __init__(self) -> None:
        self._dates: List[datetime.date] = []
        self._entries: Dict[datetime.date, List[Entry]] = {}
        self.t_raw_delta = datetime.timedelta()
        self.total_delta = datetime.timedelta()
        self.round_delta = datetime.timedelta()

    def add_entry(self, entry: Entry) -> None:
        if entry.date not in self._entries:
            self._entries[entry.date] = []
            self._dates.append(entry.date)
        self._entries[entry.date].append(entry)

        self.t_raw_delta += entry.t_raw_delta
        self.total_delta += entry.total_delta
        self.round_delta = self.total_delta - self.t_raw_delta

        self._resort()

    def _resort(self) -> None:
        self._dates.sort()
        for date in self._dates:
            self._entries[date].sort(key=operator.attrgetter('start_time'))

    @property
    def is_empty(self) -> bool:
        return len(self._entries) == 0

    @property
    def sequential(self) -> Iterator[Entry]:
        for date in self._dates:
            for entry in self._entries[date]:
                yield entry

    def employer_report(self) -> Iterator[AggregatedEmployer]:
        days: Dict[datetime.date, Dict[Employer, Dict[str, datetime.timedelta]]] = {}

        for date in self._dates:
            for entry in self._entries[date]:
                if date not in days:
                    days[date] = {}
                employer = entry.task.project.employer
                if employer not in days[date]:
                    days[date][employer] = {
                        'total_delta': datetime.timedelta()
                    }
                days[date][employer]['total_delta'] += entry.total_delta

        dates = list(days.keys())
        dates.sort()
        for date in dates:
            for employer in days[date]:
                yield AggregatedEmployer(
                    date=date,
                    total_delta=days[date][employer]['total_delta'],
                    employer=employer,
                )

    def project_report(self) -> Iterator[AggregatedProject]:
        days: Dict[datetime.date, Dict[Project, Dict[str, datetime.timedelta]]] = {}

        for date in self._dates:
            for entry in self._entries[date]:
                if date not in days:
                    days[date] = {}
                project = entry.task.project
                if project not in days[date]:
                    days[date][project] = {
                        'total_delta': datetime.timedelta()
                    }
                days[date][project]['total_delta'] += entry.total_delta

        dates = list(days.keys())
        dates.sort()
        for date in dates:
            for project in days[date]:
                yield AggregatedProject(
                    date=date,
                    total_delta=days[date][project]['total_delta'],
                    project=project,
                )

    def task_report(self) -> Iterator[AggregatedTask]:
        days: Dict[datetime.date, Dict[Project, Dict[Task, Dict[str, datetime.timedelta]]]] = {}

        for date in self._dates:
            for entry in self._entries[date]:
                if date not in days:
                    days[date] = {}
                project = entry.task.project
                task = entry.task
                if project not in days[date]:
                    days[date][project] = {}
                if task not in days[date][project]:
                    days[date][project][task] = {
                        'total_delta': datetime.timedelta()
                    }
                days[date][project][task]['total_delta'] += entry.total_delta

        dates = list(days.keys())
        dates.sort()
        for date in dates:
            for project in days[date]:
                for task in days[date][project]:
                    yield AggregatedTask(
                        date=date,
                        total_delta=days[date][project][task]['total_delta'],
                        task=task,
                    )

    def daily_report(self) -> Iterator[AggregatedDay]:
        days: Dict[datetime.date, Dict[str, datetime.timedelta]] = {}

        for date in self._dates:
            for entry in self._entries[date]:
                if date not in days:
                    days[date] = {
                        'total_delta': datetime.timedelta()
                    }
                days[date]['total_delta'] += entry.total_delta

        dates = list(days.keys())
        dates.sort()
        for date in dates:
            yield AggregatedDay(
                date=date,
                total_delta=days[date]['total_delta']
            )

    def aggregated_text_report(self) -> Iterator[AggregatedTextEntry]:
        report: Dict[Task, str] = {}
        delta: Dict[Task, datetime.timedelta] = {}
        for date in self._dates:
            for entry in self._entries[date]:
                if entry.task not in report:
                    report[entry.task] = ""
                    delta[entry.task] = datetime.timedelta()
                if entry.text is not None:
                    report[entry.task] += entry.text
                delta[entry.task] += entry.total_delta

        tasks = list(report.keys())
        tasks.sort(key=lambda task: task.name)
        for task in tasks:
            yield AggregatedTextEntry(
                task=task,
                text=report[task],
                total_delta=delta[task],
            )


class Employer(EntryList):
    def __init__(self, name: str) -> None:
        self.name = name
        self.projects: List['Project'] = []
        super().__init__()

    def get_project_by_name(self, name: str) -> Optional['Project']:
        for project in self.projects:
            if project.name == name:
                return project
        return None


class Project(EntryList):
    def __init__(self, employer: Employer, name: str) -> None:
        self.employer = employer
        self.name = name
        self.tasks: List['Task'] = []
        super().__init__()

    def get_task_by_name(self, name: str) -> Optional['Task']:
        for task in self.tasks:
            if task.name == name:
                return task
        return None

    def __str__(self) -> str:
        return self.name


class Task(EntryList):
    def __init__(self, project: Project, name: str, title: str, url: str) -> None:
        self.project = project
        self.name = name
        self.title = title or name
        self.url = url
        super().__init__()

    def __str__(self) -> str:
        return self.title


class Entries:
    def __init__(self, *, date_range: DateRange, location: Optional[str], files: List[str]) -> None:
        self._date_range = date_range
        self._location = location
        self._files = files
        self._dates: List[datetime.date] = []
        # self.t_raw_delta = datetime.timedelta()
        # self.total_delta = datetime.timedelta()
        self.all = EntryList()
        self._employers: List[Employer] = []
        self._read()

    @property
    def employers(self) -> List[Employer]:
        return self._employers

    def _read(self) -> None:
        def load_projects(root: Dict[str, Any], employer: Employer) -> None:
            for project_name, project_details in root["projects"].items():
                project = Project(
                    employer=employer,
                    name=project_name,
                )
                employer.projects.append(project)
                for task_name, task_details in project_details["tasks"].items():
                    task = Task(
                        project=project,
                        name=task_name,
                        title=task_details.get('title'),
                        url=task_details.get('url'),
                    )
                    project.tasks.append(task)

        current_datetime = datetime.datetime.now()
        start_range = self._date_range[0]
        stop_range = self._date_range[1]

        self.start_date = start_range
        self.stop_date = stop_range

        employers: Dict[str, Employer] = {}

        self._employers = []
        for filename in self._files:
            with open(filename) as stream:
                root = yaml.safe_load(stream)

            employer_name = root["employer"]
            period = parse_delta(root["period"])

            if employer_name in employers:
                employer = employers[employer_name]
            else:
                employer = Employer(
                    name=employer_name
                )
                employers[employer_name] = employer
                self._employers.append(employer)

            load_projects(root, employer)

            location = None
            previous_stop_dt = None
            for prev_entry, entry, next_entry in previous_and_next(root["entries"]):
                if 'date' in entry:
                    date = entry['date']
                else:
                    date = date

                if 'location' in entry:
                    location = entry['location']

                if 'project' in entry:
                    project_name = entry['project']
                    task_name = None
                if project_name is None:
                    raise RuntimeError('%s: No project given for %s' % (filename, entry))

                if 'task' in entry:
                    task_name = entry['task']
                if task_name is None:
                    raise RuntimeError('%s: No task given for %s' % (filename, entry))

                project: Optional[Project] = employer.get_project_by_name(project_name)
                if project is None:
                    raise RuntimeError("Unknown project '%s'" % project_name)

                task = project.get_task_by_name(task_name)
                if task is None:
                    raise RuntimeError("Unknown project '%s' task '%s'" % (project, task_name))

                if next_entry is None:
                    next_entry_same_day = False
                elif 'date' in next_entry and next_entry['date'] != date:
                    next_entry_same_day = False
                else:
                    next_entry_same_day = True

                if 'start' not in entry:
                    if 'stop' in entry and not next_entry_same_day:
                        continue
                    raise RuntimeError('%s: Cannot get start time for %s' % (filename, entry))
                entry_start_t = parse_time(entry['start'])

                if 'stop' not in entry:
                    assert next_entry is not None
                    if next_entry_same_day and 'start' in next_entry:
                        entry_stop_t = parse_time(next_entry['start'])
                    else:
                        raise RuntimeError('%s: Cannot get stop time for %s' % (filename, entry))
                else:
                    entry_stop_t = parse_time(entry['stop'])

                if 'break' in entry:
                    entry_break = parse_delta(entry['break'])
                else:
                    entry_break = datetime.timedelta()

                entry_start_dt = datetime.datetime.combine(date, entry_start_t)
                entry_stop_dt = datetime.datetime.combine(date, entry_stop_t)

                assert entry_stop_dt >= entry_start_dt
                if entry.get('future', False):
                    if entry_start_dt < current_datetime:
                        raise RuntimeError('%s: Future entry %s starts in the past' % (filename, entry_start_dt))
                else:
                    if entry_start_dt.date() > current_datetime.date():
                        raise RuntimeError('%s: Entry %s starts in the future' % (filename, entry_start_dt))
                    if entry_stop_dt.date() > current_datetime.date():
                        raise RuntimeError('%s: Entry %s stops in the future' % (filename, entry_start_dt))

                if previous_stop_dt is not None:
                    if entry_start_dt < previous_stop_dt:
                        raise RuntimeError(
                            '%s: Entry %s starts before previous entry stops %s'
                            % (filename, entry_start_dt, previous_stop_dt))

                previous_stop_dt = entry_stop_dt

                bill_date = date
                if 'bill_date' in entry:
                    bill_date = entry['bill_date']

                if self._location is not None and location != self._location:
                    continue
                if start_range and bill_date < start_range:
                    continue
                if stop_range and bill_date > stop_range:
                    continue

                entry_t_raw_delta = entry_stop_dt - entry_start_dt - entry_break
                entry_total_delta = round_timedelta(entry_t_raw_delta, period)
                entry_round_delta = entry_total_delta - entry_t_raw_delta

                if entry_t_raw_delta < datetime.timedelta(0):
                    raise RuntimeError(
                        '%s: Entry %s  has negative delta'
                        % (filename, entry_start_dt))

                if 'ignore' not in entry:
                    entry = Entry(
                        task=task,
                        date=date,
                        text=entry.get('text'),
                        start_time=entry_start_t,
                        stop_time=entry_stop_t,
                        break_delta=entry_break,
                        t_raw_delta=entry_t_raw_delta,
                        round_delta=entry_round_delta,
                        total_delta=entry_total_delta,
                    )
                    employer.add_entry(entry)
                    project.add_entry(entry)
                    task.add_entry(entry)
                    self.all.add_entry(entry)

    @property
    def projects(self) -> Iterator[Project]:
        for employer in self._employers:
            for project in employer.projects:
                if not project.is_empty:
                    yield project


def report(date_range: DateRange, location: Optional[str], files: List[str], template_name: str) -> None:
    home_dir = os.path.dirname(os.path.realpath(__file__))
    template_dir = os.path.join(home_dir, 'templates')
    loader = ibis.loaders.FileLoader(template_dir)
    template = loader(template_name)
    output = template.render({
        'entries': Entries(date_range=date_range, location=location, files=files),
    })
    sys.stdout.write(output)


def main() -> None:
    parser = argparse.ArgumentParser(description='Process time sheet.')
    parser.add_argument("-d", "--date", dest="date")
    parser.add_argument("-l", "--location", dest="location")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-D", "--day", dest="day", action="store_true")
    group.add_argument("-1", "--1week", dest="one", action="store_true")
    group.add_argument("-2", "--2week", dest="two", action="store_true")
    group.add_argument("-m", "--month", dest="month", action="store_true")
    group.add_argument("-f", "--financial_year", dest="financial_year", action="store_true")

    subparsers = parser.add_subparsers(dest='subparser')

    parser_a = subparsers.add_parser(
        'report', help="Generate complete report.")
    parser_a.add_argument("-t", "--template", dest="template_name", default="report.txt")
    parser_a.add_argument('files', nargs='+', help='Files to load.')

    kwargs = vars(parser.parse_args())

    d_string = kwargs.pop('date', None)
    if d_string is None:
        date = datetime.date.today()
    else:
        date = parse_date(d_string)

    date_range = get_date_range(
        date=date,
        day=kwargs.pop('day', None),
        one=kwargs.pop('one', None),
        two=kwargs.pop('two', None),
        month=kwargs.pop('month', None),
        financial_year=kwargs.pop('financial_year', None),
    )
    kwargs['date_range'] = date_range
    task = kwargs.pop('subparser', None)
    if task is not None:
        globals()[task](**kwargs)


if __name__ == "__main__":
    main()
