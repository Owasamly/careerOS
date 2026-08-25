'use client';

import { Document, Link, Page, StyleSheet, Text, View, pdf } from '@react-pdf/renderer';
import type { ReactNode } from 'react';
import type { ResumeData } from './resume-engine';

const styles = StyleSheet.create({
  page: { padding: 38, fontFamily: 'Helvetica', fontSize: 9.5, lineHeight: 1.45, color: '#17211d' },
  header: { borderBottomWidth: 2, borderBottomColor: '#176b52', paddingBottom: 13, marginBottom: 16 },
  name: { fontSize: 24, lineHeight: 1.16, fontFamily: 'Helvetica-Bold', color: '#102c24' },
  headline: { fontSize: 11.5, lineHeight: 1.3, color: '#176b52', marginTop: 5 },
  contact: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 8, color: '#52615b' },
  section: { marginBottom: 13 },
  sectionTitle: { fontSize: 10, fontFamily: 'Helvetica-Bold', textTransform: 'uppercase', letterSpacing: 1.3, color: '#176b52', marginBottom: 6 },
  item: { marginBottom: 8 },
  itemHead: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  itemTitle: { fontFamily: 'Helvetica-Bold', fontSize: 10.5 },
  date: { color: '#64736d', fontSize: 8.5 },
  detail: { color: '#52615b' },
  bullet: { marginLeft: 9, marginTop: 2 },
  skills: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  pill: { backgroundColor: '#edf5f1', paddingHorizontal: 5, paddingVertical: 2.5, borderRadius: 3, fontSize: 8.7 },
  link: { color: '#176b52', textDecoration: 'none' },
});

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>;
}

export function ResumeDocument({ data }: { data: ResumeData }) {
  const contact = [data.basics.email, data.basics.phone, data.basics.location].filter(Boolean);
  return (
    <Document title={`${data.basics.name || 'Candidate'} CV`} author={data.basics.name || 'Candidate'}>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.name}>{data.basics.name || 'Candidate name'}</Text>
          {data.basics.headline && <Text style={styles.headline}>{data.basics.headline}</Text>}
          <View style={styles.contact}>{contact.map((item) => <Text key={item}>{item}</Text>)}{data.basics.website && <Link style={styles.link} src={data.basics.website}>{data.basics.website}</Link>}</View>
        </View>
        {data.summary && <Section title="Profile"><Text>{data.summary}</Text></Section>}
        {!!data.experience.length && <Section title="Experience">{data.experience.map((item, index) => <View style={styles.item} key={`${item.company}-${index}`} wrap={false}><View style={styles.itemHead}><Text style={styles.itemTitle}>{[item.position, item.company].filter(Boolean).join(' · ')}</Text><Text style={styles.date}>{item.date}</Text></View>{item.summary && <Text style={styles.detail}>{item.summary}</Text>}{item.highlights.map((line) => <Text style={styles.bullet} key={line}>• {line}</Text>)}</View>)}</Section>}
        {!!data.skills.length && <Section title="Technical Skills"><View style={styles.skills}>{data.skills.flatMap((group) => group.keywords.length ? group.keywords.map((keyword) => `${group.name}: ${keyword}`) : [group.name]).map((skill) => <Text style={styles.pill} key={skill}>{skill}</Text>)}</View></Section>}
        {!!data.projects.length && <Section title="Projects">{data.projects.map((item, index) => <View style={styles.item} key={`${item.name}-${index}`} wrap={false}><Text style={styles.itemTitle}>{item.name}</Text>{item.description && <Text>{item.description}</Text>}{item.keywords.length > 0 && <Text style={styles.detail}>{item.keywords.join(' · ')}</Text>}</View>)}</Section>}
        {!!data.education.length && <Section title="Education">{data.education.map((item, index) => <View style={styles.item} key={`${item.institution}-${index}`} wrap={false}><View style={styles.itemHead}><Text style={styles.itemTitle}>{[item.degree, item.institution].filter(Boolean).join(' · ')}</Text><Text style={styles.date}>{item.date}</Text></View>{item.summary && <Text style={styles.detail}>{item.summary}</Text>}</View>)}</Section>}
      </Page>
    </Document>
  );
}

export async function downloadResumePdf(data: ResumeData) {
  const blob = await pdf(<ResumeDocument data={data} />).toBlob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${data.basics.name || 'adapted-cv'}.pdf`.replace(/[^a-z0-9.-]+/gi, '-').toLowerCase();
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
