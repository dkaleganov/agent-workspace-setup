# Group patterns

For the agent. A pattern is a way to split the AI home into groups. Use this page when the owner names two or more kinds of work at setup, or asks to "rethink my groups". With one thing named, use ours and skip this page.

**No field is built in.** The skill carries no list of categories for any trade, and the patterns work the same for a shop, a studio, a lab, a household or a portfolio of rentals. What you know about the owner's field helps you ask a better question and spot a missing group. The names and the groups still come from what this owner says.

## The consult

1. **Read three things from what the owner said:**
   - How many separate lines of work do they run? A line is something that goes on, such as a business, a job or a household.
   - Does the same work repeat for each one of something they have several of: clients, cases, courses, products, properties, events?
   - Are there one-off projects that belong to no line?
2. **Ask at most one follow-up,** and only when one of the three is unclear.
3. **Recommend one pattern** from the table, with one line on why it fits.
4. **Build the groups from the owner's own words.** Write `pattern` and `groups` into the answers file.
5. **Show the preview as printed.** It names the pattern, and the last line of its block offers ours: keep that line. The owner can change a name, drop a group or pick another pattern. A change means a new preview.

## The four patterns

| Pattern | `pattern` | The groups | Fits when | Weak when |
|---|---|---|---|---|
| By status | `status` | Projects that finish, Areas that go on, Data. These are ours | One person, varied work, and the question is "what is active?" | Several businesses: each one ends up split across groups |
| By line of work | `lines` | One group for each lasting line of work | Two or more separate lines | A one-off project belongs to no line |
| One for each | `each` | A group for a kind of thing the owner has several of, with one work folder for each one | The same work repeats for each one | Work that isn't about one of them |
| Mixed | `mixed` | Groups by line or "one for each", plus Projects for one-offs, plus Data | More than one line, and one-off projects too | The owner wants the fewest groups |

Made-up examples, each from a different field:

- **By status:** a teacher planning a course and a move. `Projects`, `Areas`, `Data`.
- **By line of work:** someone with a day job, a side business and a household. `Day-job`, `Side-business`, `Household`.
- **One for each:** a freelance designer with six clients. `Clients`, with one work folder for each client.
- **Mixed:** a researcher who runs three studies, teaches two courses and is writing a book. `Studies` and `Courses`, with one work folder for each. `Projects` for the book. `Data`.
- **Mixed, another field:** someone who rents out two homes and is building a third. `Rentals`, with one work folder for each home. `Builds`. `Data`.
- **Mixed, another field:** a bakery owner with a shop, wholesale customers and a second shop to open. `Shop`, `Wholesale` with one work folder for each customer, `Projects` for the opening.

## Rules for every pattern

- **Groups the owner names themselves are used exactly as given.** Add none of ours to them, not even Data, unless they ask. The patterns are for when the owner describes their work and leaves the groups to you.
- **Names come from the owner's words.** If they say "the flats", the group isn't "Real-estate-assets".
- **A group is named for lasting work.** Never for a year, a tool or one person, unless the owner asks. The script adds a note when a name holds a year.
- **Time goes into file names,** never into a group's name.
- **Each group gets two lines:** `about`, what goes there, and `not_for`, what doesn't. Write `not_for` wherever two groups could be confused.
- **Three to five groups.** Eight is the most a home holds besides the Inbox.
- **`work` says whether the group's work finishes or goes on.** A group that holds both is `ongoing`: each piece of work is closed and archived when it is done.
- **Never take a layout from a published or paid system,** and never propose a ready-made list of categories for a field. The groups come from this owner.

## In the answers file

```json
{"pattern": "mixed",
 "groups": [
   {"name": "Clients", "about": "One folder for each client I design for.",
    "not_for": "My own products.", "work": "ongoing"},
   {"name": "Courses", "about": "One folder for each run of a course I teach.", "work": "finishes"},
   {"name": "Projects", "about": "One-off work that belongs to no client or course.", "work": "finishes"},
   {"name": "Data", "about": "Libraries agents read."}],
 "work": [{"title": "Book on brand design", "group": "Projects", "purpose": "Write the book."}]}
```

`pattern` is optional. Leave it and `groups` out for ours. The names in this example are made up.

## Rethink my groups

For a workspace that exists. Nothing changes before the owner approves.

1. Run `group list`. It shows each group, its lines and the recorded pattern.
2. Ask what has changed in the owner's work, and run the consult above.
3. Propose only what the script can do: `group add` for a new group, `group describe` for a new line, and `move <number> --to "<group>"` for a work folder that belongs elsewhere.
4. The script never renames or removes a group folder. If a group is no longer used, say so and leave it. An empty group does no harm.

## Where the ideas come from

The patterns are this skill's own, in wording and design. The ideas behind them: sorting by what you act on, from Tiago Forte's PARA; naming for lasting functions, from records management practice; and a folder for each client with the same inside, from Johnny.Decimal's public video on client work.
