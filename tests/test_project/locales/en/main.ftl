
page-title = This is the title

youve-clicked = You've clicked { $count ->
              [one]    once
             *[other]  { $count } times
           }.

enter-name = Please enter your name below

your-name-is = Your name is { $name }.

your-country-is = Your country is { $country }.

complex-info-header = Complex Info

# The generated complexInfo function should have a type signature
# that includes the $name arg:
complex-info = { your-name-is } You are wonderful


number-tests-section-title = Number tests

message-with-hard-coded-number-and-number-function = There are { NUMBER(12345) } things.

message-with-hard-coded-bare-number-literal = There are { 123456.7 } things.

message-with-number-function-and-arg = There are { NUMBER($count) } things

message-with-number-function-and-params = There are { NUMBER(7890, useGrouping: 0, minimumIntegerDigits: 2 ) } things

message-with-money = You have { NUMBER($money, currencyDisplay:"name") } in your bank.

message-with-mixed-numeric-select = You have { $count ->
    [0]       no new messages
    [one]     one new message
   *[other]   { $count } new messages
 }


date-tests-section-title = Dates tests

here-is-a-date = Here is a formatted date: { DATETIME($mydate, day: "numeric", month:"long", year:"numeric", hour:"2-digit", minute:"2-digit", second:"2-digit", hour12: 0, era:"short") }

html-tests-section-title = HTML tests

simple-text-html = Some text with this &amp; that.

tags-html = Some <b>bold text</b> and some <b>bold <i>and italic</i></b> text.

attributes-html = Some <span class="foo">highlighted text</span>.

argument-html = Hello <b>{ $username }</b>!

html-message-reference-html = { argument-html } You came back

attribute-substitution-html = <b foo="{ attribute-substitution-html.foo }">Some text</b>
                            .foo = Hello

html-attributes-test-section-title = HTML attributes

last-movement = Your last movement:

havent-moved-yet = You haven't moved yet

you-moved-left = You moved left

you-moved-right = You moved right

go-left-or-right-html = Go <a data-left>left</a> or <a data-right>right</a>
